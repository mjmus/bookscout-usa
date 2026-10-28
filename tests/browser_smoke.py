from playwright.sync_api import sync_playwright
from pathlib import Path
import subprocess,time
ROOT=Path(__file__).resolve().parents[1]
p=subprocess.Popen(['python','-m','http.server','8765','--bind','127.0.0.1','--directory',str(ROOT/'web')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(1.4)
 with sync_playwright() as playwright:
  browser=playwright.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1000})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  markup=(ROOT/'web/index.html').read_text()
  markup=markup.replace('<script src="data/seed-data.js"></script>','').replace('<script src="data/live-data.js"></script>','').replace('<script src="app.js"></script>','')
  markup=markup.replace('<link rel="stylesheet" href="app.css">','<style>'+ (ROOT/'web/app.css').read_text()+'</style>')
  page.set_content(markup,wait_until='domcontentloaded')
  page.add_script_tag(content=(ROOT/'web/data/seed-data.js').read_text())
  page.add_script_tag(content=(ROOT/'web/data/live-data.js').read_text())
  page.add_script_tag(content=(ROOT/'web/app.js').read_text())
  page.wait_for_timeout(1200)
  print('title',page.title(),'heading',page.locator('h1').inner_text(),'cards',page.locator('.listing').count())
  print('JS errors',errors)
  print('debug prefs',page.evaluate('BookScoutTest.getData().prefs.status'),'date',page.evaluate('new Date().toString()'),'past',page.evaluate('BookScoutTest.all().filter(x=>BookScoutTest.status(x)==="Past").length'))
  page.screenshot(path='/mnt/data/BookScout_USA_preview.png',full_page=False)
  page.locator('[data-nav="calendar"]').click()
  print('calendar cells',page.locator('.day').count(),'calendar name',page.locator('h1').inner_text())
  page.locator('#calState').select_option('NC')
  print('calendar NC updated',page.locator('#calState').input_value())
  page.locator('[data-nav="map"]').click()
  page.wait_for_timeout(1400)
  print('map items',page.locator('.maprow').count())
  page.locator('[data-nav="rankings"]').click()
  print('ranking page',page.locator('h1').inner_text())
  page.locator('#newISBN').fill('9780140328721')
  page.locator('#addISBN').click()
  print('isbn no info',page.locator('h2',has_text='No information').first.inner_text())
  page.locator('[data-nav="alerts"]').click()
  print('alerts',page.locator('h1').inner_text())
  page.locator('[data-nav="settings"]').click()
  print('settings',page.locator('h1').inner_text())
  print('JS errors final',errors)
  assert not errors,errors
  assert page.locator('h1').count()==1
  browser.close()
finally:p.terminate()
