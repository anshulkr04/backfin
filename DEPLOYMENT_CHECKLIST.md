# Deployment Checklist - Company Management System

## 🎯 Pre-Deployment Checklist

### Database Setup
- [ ] Backup current database
  ```sql
  -- Create backup of critical tables
  CREATE TABLE stocklistdata_backup AS SELECT * FROM stocklistdata;
  CREATE TABLE corporatefilings_backup AS SELECT * FROM corporatefilings;
  ```

- [ ] Run Role-Based Review System migration
  ```bash
  # In Supabase SQL Editor:
  # Execute: verification_system/ROLE_BASED_REVIEW_SYSTEM.sql
  ```

- [ ] Run Company Management System migration
  ```bash
  # In Supabase SQL Editor:
  # Execute: src/services/exchange_data/company_management/COMPANY_VERIFICATION_SCHEMA.sql
  ```

- [ ] Verify all tables created
  ```sql
  -- Check tables exist
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema = 'public' 
  AND table_name IN (
    'admin_users',
    'admin_sessions',
    'corporatefilings',
    'verification_audit_log',
    'company_changes_pending',
    'company_changes_audit_log',
    'stocklistdata'
  );
  ```

- [ ] Verify all functions created
  ```sql
  -- Check functions exist
  SELECT routine_name FROM information_schema.routines 
  WHERE routine_schema = 'public' 
  AND routine_name IN (
    'log_verification_change',
    'log_company_change',
    'apply_company_change'
  );
  ```

- [ ] Verify all views created
  ```sql
  -- Check views exist
  SELECT table_name FROM information_schema.views 
  WHERE table_schema = 'public' 
  AND table_name IN (
    'review_queue',
    'verification_queue',
    'company_verification_queue',
    'company_changes_ready_to_apply',
    'company_changes_stats'
  );
  ```

### User Setup
- [ ] Create admin users
  ```sql
  -- Update existing user to admin
  UPDATE admin_users SET role = 'admin' WHERE email = 'your-admin@email.com';
  
  -- Verify role assignment
  SELECT email, role FROM admin_users WHERE role = 'admin';
  ```

- [ ] Test authentication
  ```bash
  # Test login and verify role in JWT token
  curl -X POST http://localhost:5002/api/admin/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@email.com","password":"password"}' \
    | jq '.access_token' | base64 -d
  ```

### Application Deployment
- [ ] Update dependencies
  ```bash
  cd /Users/anshulkumar/backfin/verification_system
  pip install -r requirements.txt
  ```

- [ ] Verify environment variables
  ```bash
  # Check .env file has:
  grep -E "SUPABASE_URL2|SUPABASE_SERVICE_ROLE_KEY|JWT_SECRET_KEY|GEMINI_API_KEY" .env
  ```

- [ ] Rebuild Docker container
  ```bash
  cd /Users/anshulkumar/backfin/verification_system
  docker-compose down
  docker-compose build --no-cache
  docker-compose up -d
  ```

- [ ] Check container health
  ```bash
  docker-compose ps
  docker-compose logs -f verification-api
  ```

- [ ] Verify API is running
  ```bash
  curl http://localhost:5002/health
  curl http://localhost:5002/docs
  ```

### Testing Phase 1: Announcement Verification
- [ ] Test get unverified announcements
  ```bash
  TOKEN="your-jwt-token"
  curl -X GET "http://localhost:5002/api/admin/announcements?verified=false&page=1&page_size=10" \
    -H "Authorization: Bearer $TOKEN"
  ```

- [ ] Test verify announcement
  ```bash
  curl -X POST "http://localhost:5002/api/admin/announcements/{corp_id}/verify" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Test verification"}'
  ```

- [ ] Test date filtering
  ```bash
  curl -X GET "http://localhost:5002/api/admin/announcements?start_date=2025-11-01&end_date=2025-11-21" \
    -H "Authorization: Bearer $TOKEN"
  ```

- [ ] Test category filtering
  ```bash
  curl -X GET "http://localhost:5002/api/admin/announcements/financial-results?page=1" \
    -H "Authorization: Bearer $TOKEN"
  ```

### Testing Phase 2: Review Queue (Admin)
- [ ] Test send to review
  ```bash
  ADMIN_TOKEN="admin-jwt-token"
  curl -X POST "http://localhost:5002/api/admin/announcements/{corp_id}/send-to-review" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Please review"}'
  ```

- [ ] Test get review queue
  ```bash
  curl -X GET "http://localhost:5002/api/admin/review-queue?page=1" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

- [ ] Test approve review
  ```bash
  curl -X POST "http://localhost:5002/api/admin/announcements/{corp_id}/review" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"action":"approve","notes":"Approved"}'
  ```

- [ ] Test reject review
  ```bash
  curl -X POST "http://localhost:5002/api/admin/announcements/{corp_id}/review" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"action":"reject","notes":"Needs corrections"}'
  ```

### Testing Phase 3: Company Management
- [ ] Install Python dependencies
  ```bash
  cd /Users/anshulkumar/backfin/src/services/exchange_data/company_management
  pip install pandas numpy supabase python-dotenv
  ```

- [ ] Test change detection (dry run)
  ```bash
  python detect_changes.py --source-dir ../exchange_data_files/stocklistdata --stats-only
  ```

- [ ] Test change detection (actual submission)
  ```bash
  python detect_changes.py --source-dir ../exchange_data_files/stocklistdata
  ```

- [ ] Verify changes submitted
  ```sql
  SELECT * FROM company_changes_pending 
  WHERE status = 'pending' 
  ORDER BY submitted_at DESC 
  LIMIT 10;
  ```

- [ ] Test get pending changes
  ```bash
  curl -X GET "http://localhost:5002/api/admin/company-changes/pending?page=1" \
    -H "Authorization: Bearer $TOKEN"
  ```

- [ ] Test get change detail
  ```bash
  curl -X GET "http://localhost:5002/api/admin/company-changes/{change_id}" \
    -H "Authorization: Bearer $TOKEN"
  ```

- [ ] Test verify change
  ```bash
  curl -X POST "http://localhost:5002/api/admin/company-changes/{change_id}/verify" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Verified from BSE website"}'
  ```

- [ ] Test reject change
  ```bash
  curl -X POST "http://localhost:5002/api/admin/company-changes/{change_id}/reject" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Invalid data"}'
  ```

- [ ] Test company change statistics
  ```bash
  curl -X GET "http://localhost:5002/api/admin/company-changes/stats" \
    -H "Authorization: Bearer $TOKEN"
  ```

- [ ] Test apply verified changes (Admin only)
  ```bash
  # CAUTION: This modifies stocklistdata!
  curl -X POST "http://localhost:5002/api/admin/company-changes/apply-verified" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Test application"}'
  ```

- [ ] Verify changes applied to stocklistdata
  ```sql
  -- Check applied changes
  SELECT * FROM company_changes_pending 
  WHERE status = 'applied' 
  ORDER BY applied_at DESC 
  LIMIT 10;
  
  -- Verify stocklistdata updated
  SELECT * FROM stocklistdata 
  WHERE symbol IN (
    SELECT symbol FROM company_changes_pending 
    WHERE status = 'applied'
  );
  ```

- [ ] Verify audit log
  ```sql
  SELECT * FROM company_changes_audit_log 
  ORDER BY performed_at DESC 
  LIMIT 20;
  ```

### Testing Phase 4: Role-Based Access
- [ ] Test verifier cannot access review queue
  ```bash
  VERIFIER_TOKEN="verifier-jwt-token"
  curl -X GET "http://localhost:5002/api/admin/review-queue" \
    -H "Authorization: Bearer $VERIFIER_TOKEN"
  # Should return 403 Forbidden
  ```

- [ ] Test verifier cannot apply company changes
  ```bash
  curl -X POST "http://localhost:5002/api/admin/company-changes/apply-verified" \
    -H "Authorization: Bearer $VERIFIER_TOKEN"
  # Should return 403 Forbidden
  ```

- [ ] Test verifier can verify announcements
  ```bash
  curl -X POST "http://localhost:5002/api/admin/announcements/{corp_id}/verify" \
    -H "Authorization: Bearer $VERIFIER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Verified"}'
  # Should succeed
  ```

- [ ] Test verifier can verify company changes
  ```bash
  curl -X POST "http://localhost:5002/api/admin/company-changes/{change_id}/verify" \
    -H "Authorization: Bearer $VERIFIER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"notes":"Verified"}'
  # Should succeed
  ```

### Monitoring Setup
- [ ] Setup application monitoring
  ```bash
  # Check logs directory
  ls -la /Users/anshulkumar/backfin/verification_system/logs/
  
  # Setup log rotation if needed
  # Setup monitoring alerts
  ```

- [ ] Create monitoring queries
  ```sql
  -- Save these queries for regular monitoring
  
  -- Unverified announcements by age
  CREATE VIEW unverified_by_age AS
  SELECT 
    DATE(timestamp) as date,
    COUNT(*) as count
  FROM corporatefilings 
  WHERE verified = false 
  GROUP BY DATE(timestamp)
  ORDER BY date DESC;
  
  -- Company changes pending over 24 hours
  CREATE VIEW stale_company_changes AS
  SELECT * FROM company_changes_pending 
  WHERE status = 'pending' 
  AND submitted_at < NOW() - INTERVAL '24 hours';
  ```

- [ ] Setup health check monitoring
  ```bash
  # Add to crontab or monitoring service
  */5 * * * * curl -f http://localhost:5002/health || alert-system
  ```

### Documentation
- [ ] Review all documentation files
  - [ ] `/verification_system/readme.md`
  - [ ] `/src/services/exchange_data/company_management/README.md`
  - [ ] `/src/services/exchange_data/company_management/QUICKSTART.md`
  - [ ] `/FEATURE_SUMMARY.md`

- [ ] Update any team wikis or documentation

- [ ] Create runbooks for common operations

### Backup & Rollback Plan
- [ ] Document rollback procedure
  ```sql
  -- Rollback plan if needed:
  
  -- 1. Restore backed up tables
  DROP TABLE stocklistdata;
  CREATE TABLE stocklistdata AS SELECT * FROM stocklistdata_backup;
  
  -- 2. Remove new columns from corporatefilings
  ALTER TABLE corporatefilings 
  DROP COLUMN IF EXISTS review_status,
  DROP COLUMN IF EXISTS sent_to_review_at,
  DROP COLUMN IF EXISTS sent_to_review_by,
  DROP COLUMN IF EXISTS review_notes,
  DROP COLUMN IF EXISTS reviewed_at,
  DROP COLUMN IF EXISTS reviewed_by;
  
  -- 3. Drop new tables
  DROP TABLE IF EXISTS company_changes_pending CASCADE;
  DROP TABLE IF EXISTS company_changes_audit_log CASCADE;
  DROP TABLE IF EXISTS verification_audit_log CASCADE;
  ```

- [ ] Test rollback procedure in staging (if available)

## 🎉 Post-Deployment Checklist

### Day 1
- [ ] Monitor error logs every 2 hours
- [ ] Check database query performance
- [ ] Verify all endpoints responding
- [ ] Monitor API response times
- [ ] Check audit logs for anomalies

### Day 2-7
- [ ] Daily review of pending changes
- [ ] Monitor verification rates
- [ ] Check for any error patterns
- [ ] Gather user feedback
- [ ] Document any issues

### Week 2
- [ ] Review all statistics
  ```sql
  -- Run comprehensive stats
  SELECT 
    COUNT(*) FILTER (WHERE verified = false) as unverified,
    COUNT(*) FILTER (WHERE verified = true) as verified,
    COUNT(*) FILTER (WHERE review_status = 'pending_review') as in_review
  FROM corporatefilings;
  
  SELECT status, COUNT(*) FROM company_changes_pending GROUP BY status;
  ```

- [ ] Performance optimization if needed
- [ ] Update documentation based on learnings
- [ ] Plan any needed improvements

## 📊 Success Metrics

### Announcement Verification
- [ ] Average time to verify: < 5 minutes
- [ ] Daily verification rate: > 90%
- [ ] Review queue size: < 10 items

### Company Management
- [ ] Pending changes: Reviewed within 24 hours
- [ ] Verification accuracy: > 99%
- [ ] Application success rate: 100%
- [ ] Audit log completeness: 100%

### System Health
- [ ] API uptime: > 99.9%
- [ ] Average response time: < 500ms
- [ ] Error rate: < 0.1%
- [ ] Database query time: < 100ms

## 🚨 Emergency Contacts

- **System Administrator:** [Name/Contact]
- **Database Administrator:** [Name/Contact]
- **Development Team:** [Contact]
- **On-Call Engineer:** [Contact]

## 📝 Notes Section

**Date:** _________________

**Deployed By:** _________________

**Issues Encountered:**
- 
- 
- 

**Resolutions:**
- 
- 
- 

**Performance Observations:**
- 
- 
- 

**Next Steps:**
- 
- 
- 

---

## ✅ Final Sign-Off

- [ ] All tests passed
- [ ] Documentation complete
- [ ] Monitoring in place
- [ ] Team trained
- [ ] Rollback plan ready
- [ ] Emergency contacts updated

**Deployment Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Completed

**Signed Off By:** _________________

**Date:** _________________

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-21
