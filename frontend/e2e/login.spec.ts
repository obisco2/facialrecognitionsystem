import { test, expect } from '@playwright/test'

// Mocked-backend e2e: fast iteration on frontend behavior without a real
// FastAPI process. See .agents/tracks/frontend-rewrite_20260822/spec.md for
// the full testing strategy, including the real-backend smoke pass.

test('login redirects to the role dashboard', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      json: { id: 1, username: 'lect1', role: 'lecturer', full_name: 'Dr. Muhammad Hisham', face_enrolled: 1 },
    })
  })
  await page.route('**/api/classes*', async (route) => {
    await route.fulfill({ json: [] })
  })

  await page.goto('/login')
  await page.getByLabel('Username').fill('lect1')
  await page.getByLabel('Password').fill('password')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page).toHaveURL(/\/lecturer$/)
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
})

test('shows an error on invalid credentials', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ status: 401, json: { detail: 'Invalid username or password' } })
  })

  await page.goto('/login')
  await page.getByLabel('Username').fill('bad')
  await page.getByLabel('Password').fill('bad')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page.getByRole('alert')).toHaveText('Invalid username or password')
})

test('command palette opens with ⌘K and navigates', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      json: { id: 1, username: 'lect1', role: 'lecturer', full_name: 'Dr. Muhammad Hisham', face_enrolled: 1 },
    })
  })
  await page.route('**/api/classes*', async (route) => {
    await route.fulfill({ json: [] })
  })

  await page.goto('/login')
  await page.getByLabel('Username').fill('lect1')
  await page.getByLabel('Password').fill('password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/lecturer$/)

  await page.keyboard.press('ControlOrMeta+k')
  await expect(page.getByRole('dialog', { name: 'Command palette' })).toBeVisible()
  await page.getByPlaceholder('Jump to…').fill('history')
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL(/\/lecturer\/history$/)
})
