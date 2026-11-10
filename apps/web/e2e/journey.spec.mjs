import { expect, test } from '@playwright/test'

const tenant = process.env.E2E_TENANT_ID
const otherTenant = process.env.E2E_OTHER_TENANT_ID

async function signIn(page, subject, tenantId, mfa) {
  await page.goto('/')
  await page.getByRole('link', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Development sign-in' })).toBeVisible()
  await page.getByLabel('Subject').fill(subject)
  if (mfa) await page.getByRole('checkbox', { name: /amr/ }).check()
  else await page.getByRole('checkbox', { name: /amr/ }).uncheck()
  await page.getByRole('button', { name: 'Continue' }).click()
  // Callback may briefly render a same-origin bridge page before /connect.
  await page.waitForURL(/\/(connect|callback)(?:\?|$)/, { timeout: 30_000 })
  if (!page.url().includes('/connect')) {
    const continueLink = page.getByRole('link', { name: 'Continue' })
    if (await continueLink.count()) await continueLink.click()
    await page.waitForURL(/\/connect(?:\?|$)/, { timeout: 30_000 })
  }
  await page.getByLabel('Tenant ID').fill(tenantId)
  await page.getByRole('button', { name: 'Open workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
}

function workspaceNav(page) {
  return page.getByRole('complementary', { name: 'Workspace navigation' })
}

test.beforeEach(async ({ page }) => {
  await page.context().clearCookies()
})

test('signed-out visit returns to sign-in', async ({ page }) => {
  await page.goto('/properties')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
})

test('create, claim, document quarantine, diligence, audit, and engines', async ({ page }) => {
  test.setTimeout(180_000)
  const label = `Interview candidate ${Date.now()}`
  const statement = `Seller described <img src=x onerror=alert(1)> for ${label}`
  const note = `Packet index incomplete for ${label}`
  let dialog = false
  page.on('dialog', () => { dialog = true })
  await signIn(page, 'alice', tenant, true)
  await page.goto('/properties/new')
  await expect(page.getByRole('heading', { name: 'Create a property record' })).toBeVisible()
  await page.getByLabel('Label').fill(label)
  await page.getByLabel('Jurisdiction').fill('Bengaluru Urban')
  await page.getByRole('button', { name: 'Save candidate' }).click()
  await expect(page.getByRole('heading', { name: label })).toBeVisible()
  const tabs = page.getByRole('navigation', { name: 'Property sections' })
  await tabs.getByRole('link', { name: 'Claims / evidence' }).click()
  await page.getByLabel('Claim statement').fill(statement)
  await page.getByRole('button', { name: 'Record unverified claim' }).click()
  await expect(page.getByText(statement, { exact: true })).toBeVisible()
  await expect(page.getByText('unverified', { exact: false }).first()).toBeVisible()
  expect(dialog).toBe(false)
  await tabs.getByRole('link', { name: 'Identifiers' }).click()
  await page.getByRole('textbox', { name: 'Identifier' }).fill('12/3')
  await page.getByRole('button', { name: 'Save identifier' }).click()
  await expect(page.getByText('12/3')).toBeVisible()
  await tabs.getByRole('link', { name: 'Documents' }).click()
  await page.locator('input[type=file]').setInputFiles({
    name: 'note.png',
    mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x70, 0x6e, 0x67]),
  })
  await page.getByRole('button', { name: 'Upload document' }).click()
  await expect(page.getByRole('region', { name: 'Private documents' }).getByText(/Quarantined/i)).toBeVisible()
  await tabs.getByRole('link', { name: 'Diligence' }).click()
  await page.getByRole('textbox', { name: 'Request title' }).fill('Ask for the packet')
  await page.getByRole('textbox', { name: 'Request note' }).fill('List the papers you hold.')
  await page.getByRole('button', { name: 'Open request' }).click()
  await expect(page.getByRole('region', { name: 'Diligence' }).getByRole('heading', { name: 'Ask for the packet' })).toBeVisible()
  await page.getByRole('region', { name: 'Diligence' }).getByLabel('Request note').fill(note)
  await page.getByRole('button', { name: 'Add note' }).click()
  await expect(page.getByText(note)).toBeVisible()
  await page.getByRole('button', { name: 'Close request' }).click()
  await expect(page.getByText(/Diligence request closed|closed/i).first()).toBeVisible()
  await tabs.getByRole('link', { name: 'Audit' }).click()
  await expect(page.getByRole('region', { name: 'Audit' }).getByText('document.quarantined')).toBeVisible()
  await workspaceNav(page).getByRole('link', { name: 'Engine directory', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Engine directory' })).toBeVisible()
  await expect(page.getByText('Property Identity & Evidence Graph')).toBeVisible()
})

test('another tenant cannot see the candidate', async ({ page }) => {
  test.setTimeout(120_000)
  const label = `Private candidate ${Date.now()}`
  await signIn(page, 'alice', tenant, true)
  await page.goto('/properties/new')
  await expect(page.getByRole('heading', { name: 'Create a property record' })).toBeVisible()
  await page.getByLabel('Label').fill(label)
  await page.getByLabel('Jurisdiction').fill('Hyderabad')
  await page.getByRole('button', { name: 'Save candidate' }).click()
  await page.getByRole('button', { name: /Sign out/ }).click()
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
  await signIn(page, 'mallory', otherTenant, true)
  await page.goto('/properties')
  await expect(page.getByRole('heading', { name: 'Properties' })).toBeVisible()
  await expect(page.getByText(label)).toHaveCount(0)
})

test('a token without the MFA claim cannot create a candidate', async ({ page }) => {
  await signIn(page, 'alice', tenant, false)
  await page.goto('/properties/new')
  await expect(page.getByRole('heading', { name: 'Create a property record' })).toBeVisible()
  await page.getByLabel('Label').fill('Should stay uncreated')
  await page.getByLabel('Jurisdiction').fill('Bengaluru Rural')
  await page.getByRole('button', { name: 'Save candidate' }).click()
  await expect(page.getByText(/MFA access token required|MFA claim does not allow|This session cannot perform/)).toBeVisible()
})
