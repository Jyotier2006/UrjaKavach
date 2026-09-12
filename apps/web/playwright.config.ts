import {defineConfig} from '@playwright/test';
// Overridable so the suite can run while another project already holds port 3000.
const PORT=process.env.E2E_PORT||'3000';
export default defineConfig({
  testDir:'./tests',timeout:60000,expect:{timeout:15000},workers:1,fullyParallel:false,
  reporter:[['list'],['json',{outputFile:'../../artifacts/metrics/browser-tests.json'}]],
  outputDir:'../../artifacts/qa/browser',
  use:{baseURL:`http://127.0.0.1:${PORT}`,viewport:{width:1440,height:1000},screenshot:'only-on-failure',trace:'retain-on-failure',launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined,args:['--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}},
  webServer:{command:`npx serve out -l ${PORT} --no-request-logging`,url:`http://127.0.0.1:${PORT}`,reuseExistingServer:false,timeout:30000},
});
