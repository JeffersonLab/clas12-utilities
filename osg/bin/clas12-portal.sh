mysql --defaults-extra-file=~/clas12-osg.cfg -Bse "use CLAS12OCR; select user_id, user, client_time, user_submission_id, run_status, scard from submissions where user_submission_id=8545"
