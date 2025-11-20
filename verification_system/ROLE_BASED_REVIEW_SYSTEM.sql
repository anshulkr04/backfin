ALTER TABLE admin_users 
ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'verifier' CHECK (role IN ('admin', 'verifier'));

ALTER TABLE corporatefilings
ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT NULL CHECK (review_status IN (NULL, 'pending_review', 'approved', 'rejected')),
ADD COLUMN IF NOT EXISTS sent_to_review_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sent_to_review_by UUID REFERENCES admin_users(id),
ADD COLUMN IF NOT EXISTS review_notes TEXT,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES admin_users(id);

CREATE TABLE IF NOT EXISTS verification_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    corp_id UUID REFERENCES corporatefilings(corp_id) ON DELETE CASCADE,
    user_id UUID REFERENCES admin_users(id),
    action TEXT NOT NULL CHECK (action IN ('verified', 'unverified', 'sent_to_review', 'approved', 'rejected', 'updated')),
    old_values JSONB,
    new_values JSONB,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_review_status ON corporatefilings(review_status) WHERE review_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_corporatefilings_verified_review ON corporatefilings(verified, review_status);
CREATE INDEX IF NOT EXISTS idx_verification_audit_log_corp_id ON verification_audit_log(corp_id);
CREATE INDEX IF NOT EXISTS idx_verification_audit_log_user_id ON verification_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_verification_audit_log_created_at ON verification_audit_log(created_at DESC);

CREATE OR REPLACE FUNCTION log_verification_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.verified IS DISTINCT FROM NEW.verified) OR 
       (OLD.review_status IS DISTINCT FROM NEW.review_status) THEN
        
        INSERT INTO verification_audit_log (
            corp_id,
            user_id,
            action,
            old_values,
            new_values,
            created_at
        ) VALUES (
            NEW.corp_id,
            NEW.verified_by,
            CASE 
                WHEN NEW.verified = true AND OLD.verified = false THEN 'verified'
                WHEN NEW.verified = false AND OLD.verified = true THEN 'unverified'
                WHEN NEW.review_status = 'pending_review' THEN 'sent_to_review'
                WHEN NEW.review_status = 'approved' THEN 'approved'
                WHEN NEW.review_status = 'rejected' THEN 'rejected'
                ELSE 'updated'
            END,
            jsonb_build_object(
                'verified', OLD.verified,
                'review_status', OLD.review_status,
                'verified_at', OLD.verified_at
            ),
            jsonb_build_object(
                'verified', NEW.verified,
                'review_status', NEW.review_status,
                'verified_at', NEW.verified_at
            ),
            NOW()
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_verification_change ON corporatefilings;
CREATE TRIGGER trigger_log_verification_change
    AFTER UPDATE ON corporatefilings
    FOR EACH ROW
    EXECUTE FUNCTION log_verification_change();

DROP VIEW IF EXISTS review_queue CASCADE;
CREATE VIEW review_queue AS
SELECT 
    cf.*,
    au.name as verified_by_name,
    au.email as verified_by_email,
    ra.name as sent_to_review_by_name,
    ra.email as sent_to_review_by_email
FROM corporatefilings cf
LEFT JOIN admin_users au ON cf.verified_by = au.id
LEFT JOIN admin_users ra ON cf.sent_to_review_by = ra.id
WHERE cf.verified = true 
  AND cf.review_status = 'pending_review'
ORDER BY cf.sent_to_review_at DESC;

DROP VIEW IF EXISTS verification_queue CASCADE;
CREATE VIEW verification_queue AS
SELECT 
    cf.*,
    CASE 
        WHEN cf.review_status = 'rejected' THEN true
        ELSE false
    END as is_rejected_from_review
FROM corporatefilings cf
WHERE cf.verified = false 
  AND (cf.review_status IS NULL OR cf.review_status = 'rejected')
ORDER BY cf.date DESC;
