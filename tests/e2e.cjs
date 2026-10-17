// AzzyAI Config X — Suite E2E (Playwright)
// Uso:    URL=http://127.0.0.1:7399 CFG=<ruta H_Config.lua> node tests/e2e.cjs
// La suite MUTA la configuración del sandbox: usa una copia desechable de USER_AI.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const URL = process.env.URL || 'http://127.0.0.1:7399';
const CFG = process.env.CFG;
if (!CFG) { console.error('Falta env CFG (ruta del H_Config.lua del sandbox)'); process.exit(2); }

const ART = path.join(__dirname, 'artifacts');
fs.mkdirSync(ART, { recursive: true });

let pass = 0, fail = 0;
const check = (name, cond, extra) => {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ FALLO: ' + name + (extra ? ' → ' + extra : '')); }
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const hideToast = () => page.evaluate(() => { const el = document.querySelector('#log'); if (el) el.style.display = 'none'; });
  await page.goto(URL);
  await page.waitForSelector('.opt', { timeout: 8000 });

  // T1 · carga
  console.log('T1 · Carga de la app');
  const optCount = await page.locator('.opt').count();
  check('grilla homúnculo renderiza (>100 filas)', optCount > 100, 'filas: ' + optCount);
  check('buscador presente', (await page.locator('#q').count()) === 1);
  await page.screenshot({ path: path.join(ART, 'hom.png') });

  // T2 · edición numérica + persistencia
  console.log('T2 · Edición numérica + persistencia');
  await page.fill('#q', 'IdleWalkDistance');
  await page.waitForTimeout(150);
  const row = page.locator('.opt[data-name="IdleWalkDistance"]');
  const before = await row.locator('input[type=number]').inputValue();
  const target = String(Number(before) === 5 ? 6 : 5);
  await row.locator('input[type=number]').fill(target);
  await row.locator('input[type=number]').dispatchEvent('change');
  const after = await row.locator('input[type=number]').inputValue();
  check('el valor NO revierte tras editarlo', after === target, 'antes=' + before + ' ahora=' + after);
  check('fila marcada ≠default', await row.evaluate(el => el.classList.contains('changed')));
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(700);
  const m = fs.readFileSync(CFG, 'utf8').match(/IdleWalkDistance\s*=\s*(\d+)/);
  check('persistido en H_Config.lua tras Apply', m && m[1] === target, 'en archivo: ' + (m && m[1]));

  // T3 · guard NaN
  console.log('T3 · Guard NaN');
  hideToast();
  await row.locator('input[type=number]').fill('');
  await row.locator('input[type=number]').dispatchEvent('change');
  await page.waitForTimeout(300);
  const toastNaN = await page.locator('#log').textContent();
  check('valor inválido rechazado con toast', /inválido/i.test(toastNaN), toastNaN.slice(0, 60));
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(600);
  const m3b = fs.readFileSync(CFG, 'utf8').match(/IdleWalkDistance\s*=\s*(\d+)/);
  check('archivo NO corrompido tras input inválido', m3b && m3b[1] === target, 'en archivo: ' + (m3b && m3b[1]));
  await row.locator('input[type=number]').fill(target);
  await row.locator('input[type=number]').dispatchEvent('change');
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(600);

  // T4 · sticky del header en tactics
  console.log('T4 · Sticky en tactics');
  await page.click('nav a[data-t="homTact"]');
  await page.waitForSelector('table tbody tr');
  await page.screenshot({ path: path.join(ART, 'tactics_top.png') });
  const cont = page.locator('div[style*="overflow"]');
  const contBox = await cont.boundingBox();
  await cont.evaluate(el => { el.scrollTop = 200; });
  const thBox = await page.locator('th').first().boundingBox();
  check('th pegado al borde del contenedor (no sobre la 2ª fila)',
        thBox && Math.abs(thBox.y - contBox.y) < 3,
        'th.y=' + (thBox && thBox.y.toFixed(1)) + ' cont.y=' + contBox.y.toFixed(1));
  await page.screenshot({ path: path.join(ART, 'tactics_scrolled.png') });

  // T5 · scroll conservado al editar
  console.log('T5 · Scroll conservado');
  const sc = await cont.evaluate(el => el.scrollTop);
  await page.locator('tbody tr').nth(3).locator('select').first().selectOption({ label: 'Ignore' });
  await page.waitForTimeout(200);
  check('scroll intacto tras editar tactic',
        (await cont.evaluate(el => el.scrollTop)) === sc);

  // T6 · validación de keys PVP
  console.log('T6 · Validación de keys PVP');
  await page.click('nav a[data-t="pvp"]');
  await page.waitForSelector('table tbody tr');
  await page.click('button:has-text("+ Añadir")');
  await page.locator('tbody tr').last().locator('td.key input').fill('INVALID_KEY');
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(700);
  const toastPvp = await page.locator('#log').textContent();
  check('key inválida rechazada con mensaje', /key inv/i.test(toastPvp), toastPvp.slice(0, 80));
  await page.locator('tbody tr').last().locator('button.danger').click();
  await page.waitForTimeout(200);
  await page.click('button.primary:has-text("Apply")');   // recuperación: apply válido
  await page.waitForTimeout(700);
  const toastRec = await page.locator('#log').textContent();
  check('apply válido tras corregir la key', /Guardado/i.test(toastRec), toastRec.slice(0, 60));
  await page.screenshot({ path: path.join(ART, 'pvp.png') });

  // T7 · extra
  console.log('T7 · Extra Options');
  await page.click('nav a[data-t="extra"]');
  await page.waitForSelector('#exH');
  check('editores extra cargan', (await page.locator('#exH').inputValue()).length > 100);

  // T8 · dropdowns de enum
  console.log('T8 · Dropdowns de enum');
  await page.click('nav a[data-t="mer"]');
  await page.waitForSelector('.opt[data-name="UseIdleWalk"]');
  const rowM = page.locator('.opt[data-name="UseIdleWalk"]');
  hideToast();
  await rowM.locator('select').selectOption('1');
  await page.waitForTimeout(150);
  const toastE = await page.locator('#log').textContent();
  check('cambiar enum NO da error de valor', !/inv/i.test(toastE), toastE.slice(0, 50));
  check('select queda en 1 (Circle)', (await rowM.locator('select').inputValue()) === '1');
  await page.click('nav a[data-t="hom"]');
  await page.waitForSelector('.opt[data-name="UseAutoHeal"]');
  const r2 = page.locator('.opt[data-name="UseAutoHeal"]');
  await r2.locator('select').selectOption('1');
  await page.waitForTimeout(100);
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(700);
  const m2 = fs.readFileSync(CFG, 'utf8').match(/UseAutoHeal\s*=\s*(\d+)/);
  check('UseAutoHeal persistido como 1', m2 && m2[1] === '1', 'archivo: ' + (m2 && m2[1]));
  await r2.locator('select').selectOption('2');
  await page.click('button.primary:has-text("Apply")');
  await page.waitForTimeout(700);
  const m3 = fs.readFileSync(CFG, 'utf8').match(/UseAutoHeal\s*=\s*(\d+)/);
  check('revertido a 2 tras el test', m3 && m3[1] === '2', 'archivo: ' + (m3 && m3[1]));

  // T9 · sin errores JS no capturados
  console.log('T9 · Errores JS');
  check('sin pageerror no capturados', errors.length === 0, errors.join(' | ').slice(0, 200));

  console.log('\n═══════ RESULTADO: ' + pass + ' OK · ' + fail + ' FALLOS ═══════');
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('EXCEPCIÓN:', e.message); process.exit(2); });
