import { expect, test } from '@playwright/test'

const tenant = process.env.E2E_TENANT_ID
const otherTenant = process.env.E2E_OTHER_TENANT_ID

async function signIn(page, subject, tenantId, mfa) {
  await page.goto('/')
  await page.getByRole('link', { name: 'Sign in' }).click()
  await page.getByLabel('Subject').fill(subject)
  if (mfa) await page.getByRole('checkbox', { name: /amr/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel('Tenant ID').fill(tenantId)
  await page.getByRole('button', { name: 'Open workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Properties you can read' })).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await page.context().clearCookies()
})

test('signed-out visit returns to sign-in', async ({ page }) => {
  await page.goto('/properties')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
})

test('create, paginate, open, and record an unverified claim', async ({ page }) => {
  const older = `Older candidate ${Date.now()}`
  const newer = `Newer candidate ${Date.now()}`
  const statement = `Seller described <img src=x onerror=alert(1)> for ${newer}`
  let dialog = false
  page.on('dialog', () => { dialog = true })
  await signIn(page, 'alice', tenant, true)
  for (const label of [older, newer]) {
    await page.getByRole('link', { name: 'New property' }).click()
    await page.getByLabel('Label').fill(label)
    await page.getByLabel('Jurisdiction').fill('Bengaluru Urban')
    await page.getByRole('button', { name: 'Save candidate' }).click()
    await expect(page.getByRole('heading', { name: label })).toBeVisible()
    await page.getByRole('link', { name: 'All readable properties' }).click()
  }
  await expect(page.getByRole('link', { name: newer })).toBeVisible()
  await expect(page.getByRole('link', { name: older })).toHaveCount(0)
  await page.getByRole('link', { name: 'Older properties' }).click()
  await expect(page.getByRole('link', { name: older })).toBeVisible()
  await page.goto('/')
  await page.getByRole('link', { name: newer }).click()
  await page.getByLabel('Statement').fill(statement)
  await page.getByRole('button', { name: 'Record unverified claim' }).click()
  await expect(page.getByText(statement, { exact: true })).toBeVisible()
  await expect(page.locator('.badge')).toHaveText('unverified')
  await expect(page.getByText('does not treat it as evidence of ownership')).toBeVisible()
  expect(dialog).toBe(false)
})

test('another tenant cannot see the candidate', async ({ page }) => {
  const label = `Private candidate ${Date.now()}`
  await signIn(page, 'alice', tenant, true)
  await page.getByRole('link', { name: 'New property' }).click()
  await page.getByLabel('Label').fill(label)
  await page.getByLabel('Jurisdiction').fill('Hyderabad')
  await page.getByRole('button', { name: 'Save candidate' }).click()
  await page.getByRole('button', { name: /Sign out/ }).click()
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
  await signIn(page, 'mallory', otherTenant, true)
  await expect(page.getByText(label)).toHaveCount(0)
})

test('a token without the MFA claim cannot create a candidate', async ({ page }) => {
  await signIn(page, 'alice', tenant, false)
  await page.getByRole('link', { name: 'New property' }).click()
  await page.getByLabel('Label').fill('Should stay uncreated')
  await page.getByLabel('Jurisdiction').fill('Bengaluru Rural')
  await page.getByRole('button', { name: 'Save candidate' }).click()
  await expect(page.getByText(/MFA claim does not allow/)).toBeVisible()
})
