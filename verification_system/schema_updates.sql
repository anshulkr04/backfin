-- Schema Updates for Verification System
-- These modifications work with your existing tables
-- Run each statement separately in Supabase SQL Editor if needed

-- 1. Add verified column to corporatefilings (if not exists)
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;

-- 2. Add verified_at column to corporatefilings (if not exists)
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE;

-- 3. Add verified_by column to corporatefilings (if not exists)
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified_by UUID;

-- 4. Add foreign key constraint for verified_by (will fail silently if exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_corporatefilings_verified_by'
    ) THEN
        ALTER TABLE public.corporatefilings 
        ADD CONSTRAINT fk_corporatefilings_verified_by 
        FOREIGN KEY (verified_by) REFERENCES admin_users(id);
    END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 5. Update verification_tasks announcement_id to TEXT type
-- (Skip if already TEXT - Supabase might handle this automatically)
ALTER TABLE public.verification_tasks
ALTER COLUMN announcement_id TYPE TEXT;

-- 6. Add comment to clarify the reference
COMMENT ON COLUMN verification_tasks.announcement_id IS 'References corporatefilings.corp_id';

-- 3. Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_verification_tasks_status ON verification_tasks(status);
CREATE INDEX IF NOT EXISTS idx_verification_tasks_assigned_to ON verification_tasks(assigned_to_user);
CREATE INDEX IF NOT EXISTS idx_verification_tasks_created_at ON verification_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_verified ON corporatefilings(verified) WHERE verified = false;
CREATE INDEX IF NOT EXISTS idx_admin_sessions_active ON admin_sessions(user_id, is_active) WHERE is_active = true;

-- 4. Add a trigger to update updated_at automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_verification_tasks_updated_at
    BEFORE UPDATE ON verification_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Add RLS (Row Level Security) policies if needed
-- Uncomment if you want to use Supabase RLS
-- ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE admin_sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE verification_tasks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE verification_edits ENABLE ROW LEVEL SECURITY;

-- 6. Create view for easy task querying
CREATE OR REPLACE VIEW verification_queue AS
SELECT 
    vt.id,
    vt.announcement_id,
    vt.status,
    vt.has_edits,
    vt.edit_count,
    vt.assigned_to_user,
    vt.assigned_at,
    vt.created_at,
    vt.updated_at,
    au.name as assigned_to_name,
    au.email as assigned_to_email,
    EXTRACT(EPOCH FROM (NOW() - vt.assigned_at))/60 as minutes_assigned,
    -- Include the current data for quick access
    vt.current_data->>'companyname' as company_name,
    vt.current_data->>'category' as category,
    vt.current_data->>'date' as announcement_date
FROM verification_tasks vt
LEFT JOIN admin_users au ON vt.assigned_to_user = au.id
WHERE vt.status != 'verified'
ORDER BY vt.created_at DESC;

-- 7. Create function to atomically claim a task
CREATE OR REPLACE FUNCTION claim_verification_task(
    p_user_id UUID,
    p_session_id UUID
)
RETURNS TABLE (
    task_id UUID,
    announcement_id TEXT,
    original_data JSONB,
    current_data JSONB
) AS $$
DECLARE
    v_task_id UUID;
BEGIN
    -- Find and lock the oldest queued task
    SELECT id INTO v_task_id
    FROM verification_tasks
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF v_task_id IS NULL THEN
        RETURN;
    END IF;
    
    -- Claim the task
    UPDATE verification_tasks
    SET 
        status = 'in_progress',
        assigned_to_user = p_user_id,
        assigned_to_session = p_session_id,
        assigned_at = NOW(),
        updated_at = NOW()
    WHERE id = v_task_id;
    
    -- Return the task data
    RETURN QUERY
    SELECT 
        vt.id,
        vt.announcement_id::TEXT,
        vt.original_data,
        vt.current_data
    FROM verification_tasks vt
    WHERE vt.id = v_task_id;
END;
$$ LANGUAGE plpgsql;

-- 8. Create function to release timed-out tasks
CREATE OR REPLACE FUNCTION release_timed_out_tasks(timeout_minutes INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    released_count INTEGER;
BEGIN
    WITH released AS (
        UPDATE verification_tasks
        SET 
            status = 'queued',
            assigned_to_user = NULL,
            assigned_to_session = NULL,
            assigned_at = NULL,
            timeout_count = timeout_count + 1,
            updated_at = NOW()
        WHERE 
            status = 'in_progress'
            AND assigned_at < NOW() - (timeout_minutes || ' minutes')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO released_count FROM released;
    
    RETURN released_count;
END;
$$ LANGUAGE plpgsql;

-- 9. Create function to verify and publish task
CREATE OR REPLACE FUNCTION verify_and_publish_task(
    p_task_id UUID,
    p_user_id UUID,
    p_notes TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_announcement_id TEXT;
    v_current_data JSONB;
    v_success BOOLEAN := FALSE;
BEGIN
    -- Get task data
    SELECT announcement_id, current_data
    INTO v_announcement_id, v_current_data
    FROM verification_tasks
    WHERE id = p_task_id AND status = 'in_progress';
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Task not found or not in progress';
    END IF;
    
    -- Update corporatefilings with verified data
    UPDATE corporatefilings
    SET 
        summary = v_current_data->>'summary',
        ai_summary = v_current_data->>'ai_summary',
        category = v_current_data->>'category',
        headline = v_current_data->>'headline',
        sentiment = v_current_data->>'sentiment',
        companyname = v_current_data->>'companyname',
        verified = TRUE,
        verified_at = NOW(),
        verified_by = p_user_id
    WHERE corp_id = v_announcement_id;
    
    -- Mark task as verified
    UPDATE verification_tasks
    SET 
        status = 'verified',
        is_verified = TRUE,
        verified_by = p_user_id,
        verified_at = NOW(),
        verification_notes = p_notes,
        updated_at = NOW()
    WHERE id = p_task_id;
    
    v_success := TRUE;
    RETURN v_success;
    
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Error verifying task: %', SQLERRM;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- 10. Add constraints for data integrity
-- This constraint may fail if it already exists or if there's existing data that violates it
-- You can skip this if you get an error
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'check_assigned_consistency'
    ) THEN
        ALTER TABLE verification_tasks
        ADD CONSTRAINT check_assigned_consistency 
        CHECK (
            (status = 'in_progress' AND assigned_to_user IS NOT NULL) OR
            (status != 'in_progress') OR
            status = 'verified'
        );
    END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Grant necessary permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON verification_tasks TO authenticated;
-- GRANT SELECT ON verification_queue TO authenticated;
-- GRANT EXECUTE ON FUNCTION claim_verification_task TO authenticated;
-- GRANT EXECUTE ON FUNCTION verify_and_publish_task TO authenticated;
