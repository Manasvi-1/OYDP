import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
test('real property/claim persistence, read grant/revocation, tenant and MFA denial',async({page})=>{
 const credentials=JSON.parse(readFileSync('.e2e/credentials.json','utf8'));
 const label='Browser candidate '+Date.now();
 async function connect(token){
   await page.goto('/');
   await page.getByLabel('Tenant ID',{exact:true}).fill(credentials.tenant);
   await page.getByLabel('API access token',{exact:true}).fill(token);
   await page.getByRole('button',{name:'Connect workspace'}).click();
   await expect(page.getByRole('button',{name:'Refresh',exact:true})).toBeEnabled();
 }
 async function disconnect(){await page.getByRole('button',{name:'Disconnect',exact:true}).click();}
 await connect(credentials.owner);
 await page.getByLabel('Property label',{exact:true}).fill(label);
 await page.getByLabel('Jurisdiction · user-entered',{exact:true}).fill('Bengaluru Urban · unresolved');
 await page.getByRole('button',{name:'Create private candidate'}).click();
 const candidate=page.getByRole('button',{name:label,exact:false});
 await expect(candidate).toBeVisible();await candidate.click();
 await page.getByLabel('Statement',{exact:true}).fill('<script>window.claimExecuted=true</script> A user assertion');
 await page.getByRole('button',{name:'Record unverified claim'}).click();
 await expect(page.locator('.statement')).toContainText('<script>');
 expect(await page.evaluate(()=>window.claimExecuted)).toBeUndefined();
 await page.getByLabel('Recipient subject',{exact:true}).fill('browser-reader');
 const expiry=new Date(Date.now()+3600000).toISOString().slice(0,16);
 await page.getByLabel('Expiry · your local time, within 30 days').fill(expiry);
 await page.getByRole('button',{name:'Grant read access',exact:true}).click();
 await expect(page.getByRole('status')).toHaveText('Read access saved.');await disconnect();
 await connect(credentials.reader);await candidate.click();
 await expect(page.locator('.statement')).toContainText('A user assertion');
 await page.getByLabel('Statement',{exact:true}).fill('Reader cannot write');
 await page.getByRole('button',{name:'Record unverified claim'}).click();
 await expect(page.getByRole('status')).toHaveText('Property or recipient unavailable.');await disconnect();
 await connect(credentials.withoutMfa);await candidate.click();
 await page.getByLabel('Statement',{exact:true}).fill('No MFA cannot write');
 await page.getByRole('button',{name:'Record unverified claim'}).click();
 await expect(page.getByRole('status')).toHaveText('Permission or MFA required.');await disconnect();
 await connect(credentials.outsider);
 await expect(page.getByRole('status')).toHaveText('Permission or MFA required.');
 await expect(candidate).toHaveCount(0);await disconnect();
 await connect(credentials.owner);await candidate.click();
 await page.getByLabel('Recipient subject to revoke',{exact:true}).fill('browser-reader');
 await page.getByRole('button',{name:'Revoke read access',exact:true}).click();
 await expect(page.getByRole('status')).toHaveText('Read access revoked.');await disconnect();
 await connect(credentials.reader);await expect(candidate).toHaveCount(0);
 await expect(page.getByText('No accessible candidates on this page.')).toBeVisible();
 expect(await page.evaluate(()=>({...localStorage}))).toEqual({});
});
