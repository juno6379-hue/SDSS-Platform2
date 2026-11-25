import test from 'node:test';
import assert from 'node:assert/strict';
import {
  LCLUC_9_CLASSES,
  classifyPixel,
  queryLandcoverAtPoint,
  generateLandcoverCanvasDataUrl,
} from './lclucLandcoverRaster.ts';

test('LCLUC_9_CLASSES contains exactly 9 standard remote sensing classes with distinct RGB', () => {
  assert.equal(LCLUC_9_CLASSES.length, 9);
  const indexes = LCLUC_9_CLASSES.map(c => c.index);
  assert.deepEqual(indexes, [0, 1, 2, 3, 4, 5, 6, 7, 8]);

  const keys = new Set(LCLUC_9_CLASSES.map(c => c.key));
  assert.equal(keys.size, 9);

  LCLUC_9_CLASSES.forEach(c => {
    assert.equal(c.rgb.length, 3);
    c.rgb.forEach(channel => {
      assert.ok(channel >= 0 && channel <= 255);
    });
  });
});

test('classifyPixel detects water on meandering river and dendritic reservoir', () => {
  // Test lake center area
  const lakePix = classifyPixel(0.36, 0.28, false, 'south_sulawesi');
  assert.equal(lakePix.classIndex, 0); // Water
  assert.equal(lakePix.className, '수체 (Water)');
  assert.equal(lakePix.color, '#2563eb');
});

test('classifyPixel models T1 forest on mountain ridges and T2 dramatic deforestation sprawl', () => {
  // Point in eastern upper slopes: in T1 it should be forest, in T2 it should be deforested/built-up
  const nx = 0.65;
  const ny = 0.55;

  const t1 = classifyPixel(nx, ny, false, 'west_java');
  const t2 = classifyPixel(nx, ny, true, 'west_java');

  assert.equal(t1.isChanged, false);
  assert.ok(t1.classIndex === 1 || t1.classIndex === 4 || t1.classIndex === 2);

  // In T2, this area transitions to built-up / deforestation red
  assert.equal(t2.classIndex, 6); // Built-up / Deforestation Red
  assert.equal(t2.isChanged, true);
  assert.equal(t2.color, '#dc2626');
  assert.equal(t2.changeTo, '시가화 (Built area)');
});

test('queryLandcoverAtPoint maps geographic [lng, lat] bounds to classification correctly', () => {
  const bounds = [118.0, -6.0, 122.0, -2.0];
  const region = 'south_sulawesi';

  // Point inside
  const res = queryLandcoverAtPoint(120.0, -4.0, bounds, region, false);
  assert.ok(res);
  assert.ok(res.classIndex >= 0 && res.classIndex <= 8);
  assert.ok(res.elevationM > 0);

  // Point outside bounds
  const out = queryLandcoverAtPoint(130.0, 0.0, bounds, region, false);
  assert.equal(out, null);
});

test('generateLandcoverCanvasDataUrl produces valid string even in Node test environment', () => {
  const url = generateLandcoverCanvasDataUrl('papua', true, [0, 1, 6]);
  assert.ok(typeof url === 'string');
  assert.ok(url.startsWith('data:image/png'));
});
