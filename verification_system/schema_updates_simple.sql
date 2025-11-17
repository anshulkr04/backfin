-- Schema Updates for Verification System (Simple Version)
-- Based on actual corporatefilings schema where corp_id is UUID
-- Run each section separately if you encounter errors

-- ========================================
-- STEP 1A: Add verified column
-- ========================================
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;

-- ========================================
-- STEP 1B: Add verified_at column
-- ========================================
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE;

-- ========================================
-- STEP 1C: Add verified_by column
-- ========================================
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS verified_by UUID;

-- ========================================
-- STEP 2: Add indexes for performance
-- ========================================

CREATE INDEX IF NOT EXISTS idx_verification_tasks_status ON verification_tasks(status);

CREATE INDEX IF NOT EXISTS idx_verification_tasks_assigned_to ON verification_tasks(assigned_to_user);

CREATE INDEX IF NOT EXISTS idx_verification_tasks_created_at ON verification_tasks(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_corporatefilings_verified ON corporatefilings(verified) WHERE verified = false;

CREATE INDEX IF NOT EXISTS idx_admin_sessions_active ON admin_sessions(user_id, is_active) WHERE is_active = true;

-- ========================================
-- STEP 3: Create update trigger function
-- ========================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- STEP 4: Create triggers
-- ========================================

DROP TRIGGER IF EXISTS update_verification_tasks_updated_at ON verification_tasks;
CREATE TRIGGER update_verification_tasks_updated_at
    BEFORE UPDATE ON verification_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_admin_users_updated_at ON admin_users;
CREATE TRIGGER update_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- STEP 5: Create view for verification queue
-- ========================================

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
    vt.current_data->>'companyname' as company_name,
    vt.current_data->>'category' as category,
    vt.current_data->>'date' as announcement_date
FROM verification_tasks vt
LEFT JOIN admin_users au ON vt.assigned_to_user = au.id
WHERE vt.status != 'verified'
ORDER BY vt.created_at DESC;

-- ========================================
-- STEP 6: Function to atomically claim a task
-- ========================================

CREATE OR REPLACE FUNCTION claim_verification_task(
    p_user_id UUID,
    p_session_id UUID
)
RETURNS TABLE (
    task_id UUID,
    announcement_id UUID,
    original_data JSONB,
    current_data JSONB
) AS $$
DECLARE
    v_task_id UUID;
BEGIN
    SELECT id INTO v_task_id
    FROM verification_tasks
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF v_task_id IS NULL THEN
        RETURN;
    END IF;
    
    UPDATE verification_tasks
    SET 
        status = 'in_progress',
        assigned_to_user = p_user_id,
        assigned_to_session = p_session_id,
        assigned_at = NOW(),
        updated_at = NOW()
    WHERE id = v_task_id;
    
    RETURN QUERY
    SELECT 
        vt.id,
        vt.announcement_id,
        vt.original_data,
        vt.current_data
    FROM verification_tasks vt
    WHERE vt.id = v_task_id;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- STEP 7: Function to release timed-out tasks
-- ========================================

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

-- ========================================
-- STEP 8: Function to verify and publish task
-- ========================================

CREATE OR REPLACE FUNCTION verify_and_publish_task(
    p_task_id UUID,
    p_user_id UUID,
    p_notes TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_announcement_id UUID;
    v_current_data JSONB;
    v_success BOOLEAN := FALSE;
BEGIN
    SELECT announcement_id, current_data
    INTO v_announcement_id, v_current_data
    FROM verification_tasks
    WHERE id = p_task_id AND status = 'in_progress';
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Task not found or not in progress';
    END IF;
    
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
