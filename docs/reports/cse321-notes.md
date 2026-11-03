# CSE 321 notes

## Transactions: publishing grades (S3-01)

Publishing an assessment runs in one transaction at PostgreSQL's default READ COMMITTED level. It first locks the assessment row (`SELECT … FOR UPDATE OF outcomes_assessment`) and the term row (`FOR NO KEY UPDATE`). It then copies every draft score to the published column with a single `UPDATE grading_grade SET published_score = score …`, stamps the assessment and writes an audit row. Concurrent publishes of the same assessment serialise on the row lock. A failure at any step rolls back every change, so students never see a partly published assessment. The test `test_crash_after_update_publishes_nothing` proves this by making the audit write fail after the UPDATE has already run.