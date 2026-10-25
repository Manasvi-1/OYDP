import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', workers:1, retries:0, timeout:45000,
  use:{baseURL:'http://127.0.0.1:3000', trace:'off', screenshot:'off', video:'off'},
  webServer:[
    {command:'cd ../.. && PYTHONPATH=apps/api:. python scripts/web_e2e_api.py',url:'http://127.0.0.1:8000/healthz',timeout:60000,reuseExistingServer:false},
    {command:'npm start',url:'http://127.0.0.1:3000',timeout:60000,reuseExistingServer:false,env:{OYDP_API_ORIGIN:'http://127.0.0.1:8000'}}
  ]
});
