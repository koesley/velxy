     persistent.retrieve(user_id,report_id,REPORTS)
    except persistent.StorageObjectNotFound:
     pass
    else:
     raise RuntimeError('Report object still exists after deletion')
   else:
    raise RuntimeError('Local report deletion is not implemented')
  except Exception:
   with db() as c:
    c.execute("UPDATE report_write_journal SET state='pending' WHERE report_id=? AND user_id=? AND state='recovering'",(report_id,user_id))
   return False
  with db() as c:
   done=c.execute("UPDATE report_write_journal SET state='cleaned' WHERE report_id=? AND user_id=? AND state='recovering'",(report_id,user_id))
   return done.rowcount == 1
 except Exception:
  return False

def store_verified_report(user_id, report_id, payload):
 """Persist report ZIP and verify the exact stored bytes before publishing DB metadata.

 This prevents a ready report row from being created when remote storage
 acknowledges an upload but fails to return intact report content.
 """
 persistent.store(user_id,report_id,payload,REPORTS)
 actual=persistent.retrieve(user_id,report_id,REPORTS)
 expected_digest=hashlib.sha256(payload).hexdigest()
 if not hmac.compare_digest(hashlib.sha256(actual).hexdigest(),expected_digest):
  raise RuntimeError('Report storage integrity verification failed')
 return expected_digest

def delivery_worker():
 """Local background queue; SMTP only when explicitly configured and user opted in."""
 last_reminder_scan=0
 while not STOP.wait(5):
  if not DELIVERY_ENABLED:continue
  # A row marked 'sending' when the process was killed mid-send (a redeploy,
  # a spin-down) would otherwise sit stuck forever: neither queue picks
  # 'sending' rows. Return abandoned rows to the queue first.
  try:
   with db() as c:
    notifications.reclaim_stale(c)
    c.execute("UPDATE deliveries SET status=CASE WHEN attempts<3 THEN 'retry'"
              " ELSE 'failed' END, next_attempt=? WHERE status='sending'"
              " AND next_attempt<=?",
              (now(), now()-notifications.STALE_SENDING_SECONDS))
  except Exception as exc:
   print('Email reclaim error:', type(exc).__name__ + ':', str(exc)[:200])
  try:
   with db() as c:
    row=c.execute("SELECT report_id,user_id,recipient,attempts FROM deliveries WHERE status IN ('queued','retry') AND next_attempt<=? AND attempts<3 ORDER BY next_attempt LIMIT 1",(now(),)).fetchone()
    if row:
     report_id,user_id,recipient,attempts=row
     c.execute("UPDATE deliveries SET status='sending', attempts=attempts+1 WHERE report_id=?",(report_id,))
   if row:
    report_bytes=persistent.retrieve(user_id,report_id,REPORTS)
    with db() as c:
     stored=c.execute("SELECT digest FROM reports WHERE id=? AND user_id=? AND status='ready'",(report_id,user_id)).fetchone()
    if not stored or not hmac.compare_digest(hashlib.sha256(report_bytes).hexdigest(),stored[0]):
     raise RuntimeError('Report integrity verification failed; email attachment withheld')
    notifications.send_mail(recipient, 'Your VELXTRIA report is ready',
     'Your requested VELXTRIA report is attached. This is a local demonstration. Do not send sensitive business information.',
     attachment=('VELXTRIA_Report.zip', report_bytes, 'application/zip'))
    with db() as c:
     c.execute("UPDATE deliveries SET status='sent',last_error='' WHERE report_id=?",(report_id,))
     c.execute("UPDATE reports SET email_status='sent' WHERE id=?",(report_id,))
  except Exception as exc:
   if 'report_id' in locals():
    retry=(attempts+1)<3
    with db() as c:
     c.execute('UPDATE deliveries SET status=?,last_error=?,next_attempt=? WHERE report_id=?',('retry' if retry else 'failed',str(exc)[:160],now()+min(3600,60*2**attempts),report_id))
     c.execute('UPDATE reports SET email_status=? WHERE id=?',('retry' if retry else 'failed',report_id))
   print('Email delivery error:', type(exc).__name__ + ':', str(exc)[:200])
  # Notifications (PRO confirmations, password resets, renewal reminders)
  # are best-effort: a failure here must never break report delivery.
  try:
   with db() as c:
    if now()-last_reminder_scan>=3600:
     notifications.scan_renewal_reminders(c)
     last_reminder_scan=now()
    while notifications.process_one(c):pass
  except Exception as exc:
   print('Email notification error:', type(exc).__name__ + ':', str(exc)[:200])

def month_start():
 d=datetime.now(timezone.utc)
 return int(datetime(d.year,d.month,1,tzinfo=timezone.utc).timestamp())

if __name__=='__main__':
 # Runtime guard: Render build checks alone cannot guarantee that the running
 # service has durable storage. Never serve paid accounts with missing config.
 if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview':
  if not persistent.REQUIRE or not persistent.REMOTE:
   raise SystemExit('Render requires persistent PostgreSQL; configure VELXTRIA_REQUIRE_PERSISTENCE=1 and VELXTRIA_DATABASE_URL')
  if not persistent.URL or not persistent.KEY:
   raise SystemExit('Render requires private report storage; configure VELXTRIA_SUPABASE_URL and VELXTRIA_SUPABASE_SERVICE_KEY')
 db().close()
 mode=os.getenv('VELXTRIA_DEPLOYMENT_MODE','local')
 if mode == 'render-preview' and not os.getenv('VELXTRIA_PREVIEW_PASSWORD'):
  raise SystemExit('Set VELXTRIA_PREVIEW_PASSWORD before starting Render preview')
 host='0.0.0.0' if mode == 'render-preview' else '127.0.0.1'
 port=int(os.getenv('PORT','8878'))
 print(f'VELXTRIA V4 {mode} portal on {host}:{port}; database={"postgresql" if persistent.REMOTE else "sqlite-local"}; storage={"private-supabase" if persistent.REMOTE else "local"}')
 if DELIVERY_ENABLED:
  Thread(target=delivery_worker,daemon=True).start()
  print('Email delivery queue enabled (' + ('Brevo' if notifications.brevo_configured() else 'SendGrid' if notifications.sendgrid_configured() else 'SMTP') + ')')
 else:print('Email not configured: reports available for download only')
 print('PRIVATE TEST ONLY — not production ready; no real customer data or payments.')
 ThreadingHTTPServer((host,port),Handler).serve_forever()
