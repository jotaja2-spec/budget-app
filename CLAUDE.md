# Budget App — Claude Reference Document

## What This Is
A personal budget dashboard for one user (Josh James, jotaja2@aol.com). Mobile-first, dark theme, fully automatic via Plaid bank sync. Built as a **single HTML file** with no build step — React 18 via CDN, Babel standalone for JSX, Supabase as the backend.

---

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React 18 (CDN), Babel Standalone, Inter font |
| Backend / DB | Supabase (PostgreSQL + Auth + Row Level Security) |
| Bank sync | Plaid (Production environment, real banks) |
| Hosting | GitHub Pages — `jotaja2-spec.github.io/budget-app` |
| Repo | `https://github.com/jotaja2-spec/budget-app.git` |
| Scheduled sync | Supabase pg_cron → `plaid-sync-scheduled` edge function, 6am Central daily |

---

## Files
```
budget-app/
├── index.html        ← ENTIRE APP. All React components, CSS, JS in one file (~2000+ lines)
├── netlify.toml      ← Legacy Netlify config (app now on GitHub Pages, ignore)
├── .netlify/         ← Legacy Netlify state (ignore)
└── CLAUDE.md         ← This file
```

**To deploy:** push to `master` → GitHub Pages auto-deploys in ~60 seconds. No build step needed.

---

## Supabase Project
- **URL:** `https://whlfnlqzfakkbjmkpfwj.supabase.co`
- **Anon key:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndobGZubHF6ZmFra2JqbWtwZndqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg1NTM2MzYsImV4cCI6MjA5NDEyOTYzNn0.DeNchaLR4RTQsVQzC_XB1PgH86AZ9MtB5yz1HV92EhM`
- Both are intentionally in the HTML source — safe because RLS protects all data

---

## Database Schema

### Tables (all have `user_id uuid REFERENCES auth.users` + RLS)

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `transactions` | id, description, amount, date, category, account, note, user_id | No `type` column — income is separate |
| `categories` | id, name, color, emoji, user_id | User's canonical category list |
| `budget_targets` | id, category, monthly_amount, user_id | PK is `id` (not category) — use delete+insert, not upsert |
| `accounts` | id, name, balance, type, plaid_account_id, user_id | `plaid_account_id` used for stable Plaid matching |
| `debts` | id, name, current_balance, original_amount, monthly_payment, interest_rate, color, promo_end, note, user_id | |
| `income_events` | id, user_id, amount, date, type (paycheck/bonus/other), account, note | |
| `savings_goals` | id, user_id, name, emoji, target_amount, current_amount, monthly_contribution, color, note, archived | |
| `fixed_items` | id, name, amount, due_day, account, category, user_id | Recurring bills |
| `quick_log_items` | id, label, category, default_amount, account, user_id | Quick-log presets |
| `settings` | id (=key), key, value, user_id | Pay frequency, per-check amount. PK is `id text` — use delete+insert |
| `plaid_items` | id, user_id, access_token, item_id, institution_name, cursor, last_synced_at | Plaid bank connections |

### CRITICAL: Settings/budget_targets upsert pattern
```js
// WRONG — upsert doesn't work (PK changed from natural key to uuid)
// RIGHT:
await db.from('settings').delete().eq('id', key).eq('user_id', uid);
await db.from('settings').insert({id: key, key, value, user_id: uid});
```

---

## Supabase Edge Functions

| Function | Auth | Purpose |
|----------|------|---------|
| `plaid-link-token` | JWT required | Creates Plaid Link token for bank connection UI |
| `plaid-exchange-token` | JWT required | Exchanges public_token → access_token, stores in plaid_items |
| `plaid-sync` | JWT required | Syncs transactions + balances for logged-in user |
| `plaid-sync-scheduled` | `x-cron-secret` header | Same as plaid-sync but called by pg_cron at 6am Central |

### Supabase Secrets Required
```
PLAID_CLIENT_ID   = (Plaid client ID)
PLAID_SECRET      = (Plaid production secret)
PLAID_ENV         = production
CRON_SECRET       = budget-sync-2026
```

### Plaid Environment
- **Production** environment — real banks
- Free trial: 10 bank connections included
- `PLAID_ENV=production` → uses `https://production.plaid.com`
- Chase requires OAuth registration (~24hr after first attempt)
- Fidelity and Apple Card cannot connect via Plaid

---

## App Architecture (index.html structure)

```
CSS variables + styles
CDN scripts (React, Babel, Supabase, Plaid)
─── SCRIPT type="text/babel" ───
Constants: SURL, SKEY, DEF_CATS, DEF_QL, DEF_ACCTS, DEF_FREQ
Helpers: fmt, fmtDec, today, addDays, monthLabel, dayLabel, nextDueDate, daysUntil
Algorithms: calcPayoffTimeline, calcSinglePayoff, calcCashFlow, calcNetWorth, findRecurring, calcRollover
Data layer: D.getAll(), D.addTx(), D.setSetting(), D.setBudget(), etc.
Auto Paycheck Logger: autoLogPaychecks() — runs on load, adds missed paychecks
Feature helpers: CashFlowCard, SpendingInsights, NetWorthCard, RecurringSection, YearInReview
Charts: DonutChart, SVGBarChart, SVGLineChart
Toast hook: useToast()
Screens: AuthScreen, SetupScreen, ClaimBanner
Modals: AddModal (expense), IncomeModal
Tabs: DashTab, BudgetTab, DebtTab, NetWorthTab, TrendsTab, TransTab, IncomeTab
Settings components: SettingsTab, PlaidItemRow, PlaidSection, MFASection, QuickLogManager, CategoryManager, AccountRow, NewAccountForm
Debt components: DebtCard, DebtForm, GoalCard, GoalForm
Budget components: BudgetInlineEdit, FixedItemRow, FixedItemForm
Transaction component: TxRow (tap-to-edit)
App (root): auth state, session, data loading, Plaid auto-sync on load
ReactDOM.createRoot render
```

---

## Bottom Nav Tabs
```
Home (dash) → Budget → Debts → Trends → Net Worth → Settings
                                                     ↑ also contains: Banks, Income, General, Customize, Data
```
- **Trans tab** exists but has no nav item — accessible via "View Transactions" buttons on Home + Settings
- **Income tab** also exists but no nav — accessible via Settings → Income subtab

---

## User Data (Josh James)
- **User ID:** `97f90958-d245-4d46-b548-b72813fb9e54`
- **Pay:** Semi-monthly (1st & 15th), $2,297.50/check post-promotion (Apr 15 2026)
- **Employer:** R1 RCM HOLDCO
- **Accounts connected via Plaid:** FNB Checking, AFCU Checking, BOA, Discover, Ally, Robinhood, PayPal
- **Pending Plaid:** Chase (OAuth registration), AMEX
- **Manual only:** Apple Card (Goldman Sachs blocks Plaid), Fidelity 401k, HSA
- **Mortgage:** AFCU, $83,167.75 @ 6.125%, $515.25 P&I + $289.12 escrow = $804.37/mo total

---

## Categories (user's actual DB categories)
Car, Debt Payoff, Eating Out, Entertainment, Gas, Groceries, Healthcare, Home, Home Improvement, Housing, Other, Personal Care, Savings, Shopping, Student Loans, Subscriptions, Utilities

**Plaid merchant overrides (sync function):**
- Sam's Club Fuel Center, Casey's, Buc-ee's, RaceTrac, Love's, Shell, Exxon, Chevron → **Gas**
- Walmart, Sam's Club → **Groceries**
- TuxMat → **Car**
- AutoZone, O'Reilly, Advance Auto → **Car**

**Plaid skip list (never import):**
- Transaction categories: INCOME, TRANSFER_IN, TRANSFER_OUT
- Description keywords: escrow, property tax, insurance disbursement
- Account subtypes: mortgage, student, auto, loan, line of credit, home equity

---

## Key Design Decisions (DO NOT UNDO)

1. **Single HTML file** — intentional, no build tooling, deploy by git push
2. **No `type` column on transactions** — income lives in `income_events` table only
3. **Plaid `plaid_account_id` on accounts** — match by ID not name, so renames don't break balance syncs
4. **Settings/budget_targets delete+insert** — PKs were restructured from natural keys to UUIDs; Supabase upsert doesn't work here
5. **Escrow transactions skipped** — escrow disbursements come from a hidden AFCU escrow account, not user spending
6. **Credit card debts tracked in `debts` table** — accounts with `type='credit'` are display-only for net worth; credit cards tracked in debts are the liability source of truth
7. **Account types:** `credit` = tracked in debts (excluded from net worth liabilities), `credit_standalone` = NOT in debts (counts as liability in net worth)
8. **Auto-paycheck logger** — runs on every app load, only adds paychecks after the last logged one (no backfill on existing data)
9. **Plaid sync always reloads data** — even when 0 new transactions (balance updates need this)
10. **RLS on all tables** — legacy NULL user_id rows visible to any authenticated user (claim banner lets user adopt them)

---

## Automatic Features
- **Plaid sync on app load** — fires as fire-and-forget, always reloads data when complete
- **6am daily sync** — pg_cron → `plaid-sync-scheduled` edge function
- **Paycheck auto-logger** — adds missed semi-monthly paychecks since last logged one
- **Credit card debt auto-update** — Plaid sync updates `debts.current_balance` when it updates matching credit accounts
- **Rename bank → updates all transactions** — PlaidItemRow rename cascades to transactions.account

---

## Current State (as of May 2026)
- ✅ Plaid production connected: FNB, AFCU, BOA, Discover, Ally, Robinhood, PayPal
- ✅ 307 transactions, all correctly categorized
- ✅ 5 active debts tracked (Mortgage, BOA Card, Chase Card, Student Loan, JCP Card)
- ✅ Cruise savings goal active
- ✅ MFA available (TOTP via authenticator app)
- ⏳ Chase pending (OAuth registration ~24hr)
- ⏳ AMEX not yet connected

---

## Known Issues / TODOs
- **Scheduled sync edge function** (`plaid-sync-scheduled`) needs updating to match latest `plaid-sync` logic whenever plaid-sync is modified
- **Apple Card** transactions are manual-only — exported from Wallet app as CSV
- **Fidelity/HSA balances** are manual — update via Net Worth tab when checking account
- **JCP Card** ($173) in debts but not connected via Plaid (Synchrony Bank, hit-or-miss)
- **Income from Plaid** is filtered out — paycheck deposits don't auto-create income_events (auto-logger handles this via settings)
- **`icon` field** on categories — old data has `icon`, new data uses `emoji`. Code handles both: `c.emoji||c.icon`

---

## Deployment
```bash
git add index.html
git commit -m "description"
git push  # GitHub Pages deploys automatically in ~60s
```
Live URL: `https://jotaja2-spec.github.io/budget-app`

---

## Local File Path
`C:\Users\joshj\OneDrive\Desktop\budget-app\index.html`
