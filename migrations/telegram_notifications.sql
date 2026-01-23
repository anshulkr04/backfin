-- ============================================================================
-- TELEGRAM NOTIFICATION SYSTEM - DATABASE MIGRATIONS
-- Run this file to set up all required tables for Telegram notifications
-- ============================================================================

-- 1. User Telegram Subscriptions
-- Links Telegram chat IDs to UserData accounts
CREATE TABLE IF NOT EXISTS public.user_telegram_subscriptions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    telegram_chat_id bigint NOT NULL UNIQUE,
    telegram_username text,
    telegram_first_name text,
    telegram_last_name text,
    is_active boolean DEFAULT true,
    verification_code text,
    verification_expires_at timestamp with time zone,
    is_verified boolean DEFAULT false,
    subscribed_at timestamp with time zone DEFAULT now(),
    unsubscribed_at timestamp with time zone,
    last_notification_at timestamp with time zone,
    notification_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT user_telegram_subscriptions_pkey PRIMARY KEY (id),
    CONSTRAINT user_telegram_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.UserData(UserID) ON DELETE CASCADE
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_telegram_subscriptions_user_id ON public.user_telegram_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_subscriptions_chat_id ON public.user_telegram_subscriptions(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_subscriptions_active ON public.user_telegram_subscriptions(is_active) WHERE is_active = true;

-- 2. Telegram Notification Log
-- Tracks all sent notifications for auditing and debugging
CREATE TABLE IF NOT EXISTS public.telegram_notification_log (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid,
    telegram_chat_id bigint NOT NULL,
    corp_id uuid,
    isin text,
    symbol text,
    company_name text,
    category text,
    notification_type text DEFAULT 'announcement' CHECK (notification_type IN ('announcement', 'insider_trading', 'corporate_action', 'deal', 'system')),
    message_text text,
    notification_status text NOT NULL DEFAULT 'pending' CHECK (notification_status IN ('pending', 'sent', 'failed', 'rate_limited', 'blocked', 'user_stopped')),
    telegram_message_id bigint,
    error_message text,
    retry_count integer DEFAULT 0,
    sent_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT telegram_notification_log_pkey PRIMARY KEY (id),
    CONSTRAINT telegram_notification_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.UserData(UserID) ON DELETE SET NULL,
    CONSTRAINT telegram_notification_log_corp_id_fkey FOREIGN KEY (corp_id) REFERENCES public.corporatefilings(corp_id) ON DELETE SET NULL
);

-- Index for querying recent notifications
CREATE INDEX IF NOT EXISTS idx_telegram_log_created_at ON public.telegram_notification_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_telegram_log_user_id ON public.telegram_notification_log(user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_log_status ON public.telegram_notification_log(notification_status);
CREATE INDEX IF NOT EXISTS idx_telegram_log_chat_id ON public.telegram_notification_log(telegram_chat_id);

-- 3. Telegram Notification Queue
-- Used for queueing notifications before sending (fallback if Redis is down)
CREATE TABLE IF NOT EXISTS public.telegram_notification_queue (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    telegram_chat_id bigint NOT NULL,
    user_id uuid,
    corp_id uuid,
    isin text,
    company_name text,
    category text,
    message_payload jsonb NOT NULL,
    priority integer DEFAULT 0,
    status text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts integer DEFAULT 0,
    max_attempts integer DEFAULT 3,
    scheduled_at timestamp with time zone DEFAULT now(),
    processed_at timestamp with time zone,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT telegram_notification_queue_pkey PRIMARY KEY (id)
);

-- Index for processing queue efficiently
CREATE INDEX IF NOT EXISTS idx_telegram_queue_status ON public.telegram_notification_queue(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_telegram_queue_scheduled ON public.telegram_notification_queue(scheduled_at) WHERE status = 'pending';

-- 4. Telegram Bot Stats (for monitoring)
CREATE TABLE IF NOT EXISTS public.telegram_bot_stats (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    date date NOT NULL UNIQUE DEFAULT CURRENT_DATE,
    total_subscribers integer DEFAULT 0,
    active_subscribers integer DEFAULT 0,
    notifications_sent integer DEFAULT 0,
    notifications_failed integer DEFAULT 0,
    notifications_rate_limited integer DEFAULT 0,
    new_subscriptions integer DEFAULT 0,
    unsubscriptions integer DEFAULT 0,
    unique_companies_notified integer DEFAULT 0,
    avg_delivery_time_ms integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT telegram_bot_stats_pkey PRIMARY KEY (id)
);

-- 5. Add telegram_enabled to user_notification_preferences if it doesn't exist
ALTER TABLE public.user_notification_preferences 
ADD COLUMN IF NOT EXISTS telegram_enabled boolean DEFAULT true;

ALTER TABLE public.user_notification_preferences 
ADD COLUMN IF NOT EXISTS telegram_categories text[];

ALTER TABLE public.user_notification_preferences 
ADD COLUMN IF NOT EXISTS telegram_quiet_start time without time zone;

ALTER TABLE public.user_notification_preferences 
ADD COLUMN IF NOT EXISTS telegram_quiet_end time without time zone;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get all Telegram subscribers for a specific ISIN (from watchlist)
CREATE OR REPLACE FUNCTION get_telegram_subscribers_for_isin(target_isin text)
RETURNS TABLE (
    user_id uuid,
    telegram_chat_id bigint,
    telegram_username text,
    email_id text
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT 
        u."UserID" as user_id,
        ts.telegram_chat_id,
        ts.telegram_username,
        u."emailID" as email_id
    FROM public.watchlistdata wd
    JOIN public."UserData" u ON wd.user_id_uuid = u."UserID"
    JOIN public.user_telegram_subscriptions ts ON u."UserID" = ts.user_id
    LEFT JOIN public.user_notification_preferences np ON u."UserID" = np.user_id
    WHERE wd.isin = target_isin
      AND ts.is_active = true
      AND ts.is_verified = true
      AND COALESCE(np.telegram_enabled, true) = true;
END;
$$ LANGUAGE plpgsql;

-- Function to update telegram stats
CREATE OR REPLACE FUNCTION update_telegram_stats()
RETURNS void AS $$
DECLARE
    today_date date := CURRENT_DATE;
BEGIN
    INSERT INTO public.telegram_bot_stats (date, total_subscribers, active_subscribers)
    SELECT 
        today_date,
        COUNT(*),
        COUNT(*) FILTER (WHERE is_active = true AND is_verified = true)
    FROM public.user_telegram_subscriptions
    ON CONFLICT (date) 
    DO UPDATE SET 
        total_subscribers = EXCLUDED.total_subscribers,
        active_subscribers = EXCLUDED.active_subscribers,
        updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old notification logs (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_telegram_logs()
RETURNS integer AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM public.telegram_notification_log
    WHERE created_at < now() - interval '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE public.user_telegram_subscriptions IS 'Links Telegram chat IDs to user accounts for notification delivery';
COMMENT ON TABLE public.telegram_notification_log IS 'Audit log of all Telegram notifications sent';
COMMENT ON TABLE public.telegram_notification_queue IS 'Fallback queue for Telegram notifications when Redis is unavailable';
COMMENT ON TABLE public.telegram_bot_stats IS 'Daily statistics for Telegram bot activity';
COMMENT ON FUNCTION get_telegram_subscribers_for_isin IS 'Returns all active Telegram subscribers who have the given ISIN in their watchlist';
