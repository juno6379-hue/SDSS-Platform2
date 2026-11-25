/**
 * LCLUC Organic Remote Sensing Land Cover Classification Raster Engine
 *
 * Generates continuous, organic, fractal-like land cover classification surfaces
 * matching authentic Sentinel-2 / Landsat remote sensing classification maps
 * (meandering dendritic water bodies, mountain ridge forest tracts,
 * organic agricultural belts, and dramatic deforestation/urban expansion frontiers).
 */

export interface LandcoverClassInfo {
  index: number;
  key: string;
  name: string;
  color: string;
  rgb: [number, number, number];
  description: string;
}

export const LCLUC_9_CLASSES: readonly LandcoverClassInfo[] = Object.freeze([
  {
    index: 0,
    key: 'water',
    name: '수체 (Water)',
    color: '#2563eb',
    rgb: [37, 99, 235],
    description: '하천, 호수, 저수지 및 연안 해역',
  },
  {
    index: 1,
    key: 'trees',
    name: '수목 (Trees)',
    color: '#15803d',
    rgb: [21, 128, 61],
    description: '자연림, 조림지 등 교목 수관 피복',
  },
  {
    index: 2,
    key: 'grass',
    name: '초지 (Grass)',
    color: '#84cc16',
    rgb: [132, 204, 22],
    description: '자연 초본 및 목초지',
  },
  {
    index: 3,
    key: 'flooded_vegetation',
    name: '침수 식생 (Flooded vegetation)',
    color: '#14b8a6',
    rgb: [20, 184, 166],
    description: '맹그로브, 소택지 및 침수 식생',
  },
  {
    index: 4,
    key: 'crops',
    name: '농경지 (Crops)',
    color: '#eab308',
    rgb: [234, 179, 8],
    description: '논, 밭 등 농업용 경작지',
  },
  {
    index: 5,
    key: 'shrub_and_scrub',
    name: '관목 (Shrub & scrub)',
    color: '#a16207',
    rgb: [161, 98, 7],
    description: '관목림 및 저목 식생',
  },
  {
    index: 6,
    key: 'built',
    name: '시가화 (Built area)',
    color: '#dc2626',
    rgb: [220, 38, 38],
    description: '건물, 도로 및 인공 시설물',
  },
  {
    index: 7,
    key: 'bare',
    name: '나지 (Bare ground)',
    color: '#a8a29e',
    rgb: [168, 162, 158],
    description: '노출 토양, 암석 및 비식생 지표',
  },
  {
    index: 8,
    key: 'snow_and_ice',
    name: '설빙 (Snow & ice)',
    color: '#a5d8f3',
    rgb: [165, 216, 243],
    description: '고산 만년설 및 빙설 지대',
  },
]);

export interface PixelClassificationResult {
  classIndex: number;
  className: string;
  color: string;
  isChanged: boolean;
  changeFrom?: string;
  changeTo?: string;
  elevationM: number;
}

/**
 * Deterministic Fractal Fractional Brownian Motion (fBm) noise
 */
function fbmNoise(nx: number, ny: number, seed: number): number {
  let val = 0;
  let amp = 0.52;
  let freq = 1.0;
  for (let i = 0; i < 4; i++) {
    const s1 = Math.sin((nx * freq * 3.14159 * 2) + seed + i * 1.7);
    const s2 = Math.cos((ny * freq * 3.14159 * 2) + seed * 1.414 + i * 2.3);
    val += amp * ((s1 * s2 + 1) / 2);
    freq *= 2.15;
    amp *= 0.48;
  }
  return Math.max(0, Math.min(1, val));
}

/**
 * String hash for deterministic regional seed
 */
function getRegionSeed(region = 'indonesia'): number {
  let h = 0;
  for (let i = 0; i < region.length; i++) {
    h = (Math.imul(31, h) + region.charCodeAt(i)) | 0;
  }
  return Math.abs(h % 1000) + 13;
}

/**
 * Computes organic remote sensing land cover class for normalized coordinate (nx, ny in [0, 1]).
 * nx: 0 (West) to 1 (East)
 * ny: 0 (North) to 1 (South)
 */
export function classifyPixel(
  nx: number,
  ny: number,
  isT2: boolean,
  region = 'default'
): PixelClassificationResult {
  const seed = getRegionSeed(region);
  const isPapua = region.toLowerCase().includes('papua');

  // 1. Natural Meandering River Geometry
  // Snakes from north-northwest to east-southeast
  const riverCenter =
    0.16 +
    0.28 * Math.sin(ny * 3.6 + 0.6) +
    0.32 * Math.pow(ny, 1.45) +
    0.05 * Math.sin(ny * 12.0);
  const riverWidth = 0.016 + 0.007 * Math.sin(ny * 6.0);
  const distToRiver = Math.abs(nx - riverCenter);

  // 2. Branched Dendritic Lake/Reservoir Geometry in Upper Left-Center
  const lakeCenterX = 0.36;
  const lakeCenterY = 0.28;
  const lakeDx = (nx - lakeCenterX) * 1.5;
  const lakeDy = (ny - lakeCenterY) * 1.1;
  const lakeAngle = Math.atan2(lakeDy, lakeDx);
  const lakeRadialDist = Math.hypot(lakeDx, lakeDy);
  // Dendritic arms using angular harmonics
  const lakeRadius =
    0.10 +
    0.045 * Math.sin(lakeAngle * 4.0) +
    0.025 * Math.cos(lakeAngle * 7.0 + 1.2) +
    0.02 * fbmNoise(nx * 8.0, ny * 8.0, seed + 5);

  const isLake = lakeRadialDist < lakeRadius;
  const isRiver = distToRiver < riverWidth;

  if (isLake || isRiver) {
    return {
      classIndex: 0,
      className: LCLUC_9_CLASSES[0].name,
      color: LCLUC_9_CLASSES[0].color,
      isChanged: false,
      elevationM: Math.round(15 + ny * 25),
    };
  }

  // 3. Realistic Topographic Elevation Model
  // Mountain ridges with fractal contours
  const elevationNorm =
    fbmNoise(nx * 3.2, ny * 3.2, seed) * 0.62 +
    fbmNoise(nx * 8.0, ny * 8.0, seed + 17) * 0.28 +
    fbmNoise(nx * 19.0, ny * 19.0, seed + 31) * 0.10;
  const elevationM = Math.round(50 + elevationNorm * 1850);

  // Mangrove along coastal / wetland borders
  const isCoastMargin = (ny < 0.08 && nx < 0.3) || (nx < 0.06 && ny < 0.4);
  if (isCoastMargin || (distToRiver < riverWidth * 2.2 && elevationNorm < 0.32)) {
    return {
      classIndex: 3,
      className: LCLUC_9_CLASSES[3].name,
      color: LCLUC_9_CLASSES[3].color,
      isChanged: false,
      elevationM: Math.round(5 + elevationNorm * 30),
    };
  }

  // Papua High Mountain Glaciers
  if (isPapua && elevationNorm > 0.88 && nx > 0.4 && nx < 0.7 && ny < 0.4) {
    return {
      classIndex: 8,
      className: LCLUC_9_CLASSES[8].name,
      color: LCLUC_9_CLASSES[8].color,
      isChanged: false,
      elevationM: Math.round(4200 + elevationNorm * 680),
    };
  }

  // 4. Initial Land Cover at T1 (2020)
  let initialClass = 1; // Default to forest
  if (elevationNorm < 0.36) {
    // Lowland agricultural basin along river
    initialClass = 4; // Crops
  } else if (elevationNorm < 0.45) {
    // Intermediate valley and foot slopes
    const grassFactor = fbmNoise(nx * 6.0, ny * 6.0, seed + 22);
    initialClass = grassFactor > 0.5 ? 2 : 4; // Grass or Crops
  } else if (elevationNorm < 0.52) {
    // Foothills / forest edge
    const agroFactor = fbmNoise(nx * 7.5, ny * 7.5, seed + 33);
    initialClass = agroFactor > 0.6 ? 5 : 1; // Plantation or Forest
  } else {
    // Upper ridges and mountain peaks
    initialClass = 1; // Forest
  }

  // Small compact initial urban core around (0.76, 0.64)
  const initialUrbanDist = Math.hypot((nx - 0.76) * 1.2, (ny - 0.64) * 0.9);
  if (initialUrbanDist < 0.07) {
    initialClass = 6;
  }

  // Active mining / bare spots at T1
  const bareSpot1 = Math.hypot(nx - 0.55, ny - 0.45) < 0.035;
  const bareSpot2 = Math.hypot(nx - 0.35, ny - 0.68) < 0.028;
  if (bareSpot1 || bareSpot2) {
    initialClass = 7;
  }

  // 5. T2 (2025) Transition Dynamics (Matches User Screenshot: Sprawling Red Deforestation & Urbanization!)
  let currentClass = initialClass;
  let isChanged = false;
  let changeFrom: string | undefined = undefined;

  if (isT2) {
    // Dramatic red sprawl extending from southeast and east across valleys and into mountain slopes
    const sprawlCenterDist = Math.hypot((nx - 0.76) * 1.05, (ny - 0.56) * 0.9);
    const sprawlFractal = fbmNoise(nx * 5.2, ny * 5.2, seed + 77);
    const riverProximity = Math.max(0, 1.0 - distToRiver * 4.5);

    // Dynamic threshold creates jagged, dendritic deforestation fronts
    const deforestFront =
      0.34 +
      0.18 * sprawlFractal +
      0.12 * riverProximity -
      Math.max(0, (elevationNorm - 0.55) * 0.7);

    // Right-hand side major deforestation / urban expansion (Class 6 #dc2626)
    if (nx > 0.48 && sprawlCenterDist < deforestFront && elevationNorm < 0.72) {
      if (initialClass !== 6) {
        currentClass = 6; // Built-up / Deforestation Red
        isChanged = true;
        changeFrom = LCLUC_9_CLASSES[initialClass].name;
      }
    } else if (sprawlCenterDist >= deforestFront && sprawlCenterDist < deforestFront + 0.065) {
      // Transition frontier buffer: Bare land (clearings) or Plantation
      const frontierNoise = fbmNoise(nx * 11.0, ny * 11.0, seed + 88);
      if (frontierNoise > 0.55 && initialClass === 1) {
        currentClass = 7; // Bare land
        isChanged = true;
        changeFrom = LCLUC_9_CLASSES[1].name;
      } else if (frontierNoise > 0.30 && initialClass === 1) {
        currentClass = 5; // Plantation
        isChanged = true;
        changeFrom = LCLUC_9_CLASSES[1].name;
      }
    } else if (distToRiver < riverWidth * 3.5 && initialClass === 2) {
      // River corridor agricultural intensification
      currentClass = 4; // Crops
      isChanged = true;
      changeFrom = LCLUC_9_CLASSES[2].name;
    }
  }

  const meta = LCLUC_9_CLASSES[currentClass] || LCLUC_9_CLASSES[1];

  return {
    classIndex: currentClass,
    className: meta.name,
    color: meta.color,
    isChanged,
    changeFrom,
    changeTo: isChanged ? meta.name : undefined,
    elevationM,
  };
}

/**
 * Generates an organic high-resolution remote sensing classification PNG data URL.
 * Automatically respects `enabledClasses` filter by writing transparent pixels for hidden classes.
 */
export function generateLandcoverCanvasDataUrl(
  region: string,
  isT2: boolean,
  enabledClasses: readonly number[],
  width = 512,
  height = 512
): string {
  if (typeof document === 'undefined') {
    // Node.js test environment mock
    return `data:image/png;base64,mock_${region}_${isT2 ? 't2' : 't1'}`;
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  const imgData = ctx.createImageData(width, height);
  const data = imgData.data;

  const enabledSet = new Set(enabledClasses);

  for (let y = 0; y < height; y++) {
    const ny = y / height;
    for (let x = 0; x < width; x++) {
      const nx = x / width;
      const res = classifyPixel(nx, ny, isT2, region);
      const idx = (y * width + x) * 4;

      if (!enabledSet.has(res.classIndex)) {
        // Transparent pixel if class is disabled
        data[idx] = 0;
        data[idx + 1] = 0;
        data[idx + 2] = 0;
        data[idx + 3] = 0;
      } else {
        const rgb = LCLUC_9_CLASSES[res.classIndex].rgb;
        data[idx] = rgb[0];
        data[idx + 1] = rgb[1];
        data[idx + 2] = rgb[2];
        data[idx + 3] = 235; // 92% base opacity for rich map presence
      }
    }
  }

  ctx.putImageData(imgData, 0, 0);
  return canvas.toDataURL('image/png');
}

/**
 * Query land cover class and change statistics at any geographic [lng, lat] coordinate.
 */
export function queryLandcoverAtPoint(
  lng: number,
  lat: number,
  bounds: [number, number, number, number],
  region: string,
  isT2: boolean
): PixelClassificationResult | null {
  const [w, s, e, n] = bounds;
  if (lng < w || lng > e || lat < s || lat > n) return null;

  const nx = (lng - w) / (e - w);
  const ny = (n - lat) / (n - s);

  return classifyPixel(nx, ny, isT2, region);
}
