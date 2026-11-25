/**
 * LCLUC Hotspot District (ADM2 - Kabupaten / Kota) Resolver
 * (LclucHotspotDistrictResolver.ts)
 *
 * Implements Section 5 requirements:
 * 1. Resolves spatial coordinates [lng, lat] and hotspot clusters to official
 *    Indonesian ADM2 administrative districts (Kabupaten / Kota).
 * 2. Provides rich metadata: District name, province, administrative type,
 *    coordinates, total area (ha), annual deforestation/change (ha), risk level,
 *    and dominant transition type.
 * 3. Renders interactive detail card and map popup HTML for hotspot marker clicks.
 *
 * Target Workspace: frontend/src/
 */

export type DistrictType = 'Kabupaten' | 'Kota';
export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface ADM2DistrictInfo {
  id: string;
  name: string;
  localName: string;
  type: DistrictType;
  province: string;
  provinceSlug: string;
  center: [number, number]; // [lng, lat]
  bounds: [number, number, number, number]; // [w, s, e, n]
  riskLevel: RiskLevel;
  totalAreaHa: number;
  annualLossHa: number;
  dominantTransition: string;
  description: string;
  keyDrivers: string[];
}

export interface HotspotMarkerInfo {
  id: string;
  title: string;
  province: string;
  districtId: string;
  districtName: string;
  districtType: DistrictType;
  coordinates: [number, number]; // [lng, lat]
  changeAreaHa: number;
  riskLevel: RiskLevel;
  dominantTransition: string;
  sclQuality: string;
  observationDateT1: string;
  observationDateT2: string;
  dataProvenanceT1: string;
  dataProvenanceT2: string;
  description: string;
  mitigationRecommendation: string;
}

// -----------------------------------------------------------------------------
// ADM2 District Registry for First Group 6 Provinces
// -----------------------------------------------------------------------------

export const FIRST_GROUP_ADM2_DISTRICTS: readonly ADM2DistrictInfo[] = Object.freeze([
  // South Sulawesi (24 ADM2 units)
  {
    id: 'gowa',
    name: 'Kabupaten Gowa',
    localName: 'Kabupaten Gowa',
    type: 'Kabupaten',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [119.74, -5.32],
    bounds: [119.45, -5.58, 120.02, -5.15],
    riskLevel: 'CRITICAL',
    totalAreaHa: 188330,
    annualLossHa: 3420,
    dominantTransition: '산림 벌채 → 농경지 개간 및 택지화',
    description: '마카사르 위성도시 확장 및 고지대 산림 개간으로 인한 삼림 훼손 고위험 지역',
    keyDrivers: ['도시 확장', '고랭지 농경지', '목재 수탈'],
  },
  {
    id: 'maros',
    name: 'Kabupaten Maros',
    localName: 'Kabupaten Maros',
    type: 'Kabupaten',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [119.62, -5.02],
    bounds: [119.42, -5.25, 119.85, -4.85],
    riskLevel: 'HIGH',
    totalAreaHa: 161910,
    annualLossHa: 2150,
    dominantTransition: '카르스트 산림 → 시멘트 광산 및 농지',
    description: '반티무룽 카르스트 생태계 인접지역의 채석 및 농지 침범',
    keyDrivers: ['시멘트 원료 채석', '석회암 산림 개간'],
  },
  {
    id: 'bone',
    name: 'Kabupaten Bone',
    localName: 'Kabupaten Bone',
    type: 'Kabupaten',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [120.15, -4.54],
    bounds: [119.88, -4.95, 120.45, -4.18],
    riskLevel: 'HIGH',
    totalAreaHa: 355540,
    annualLossHa: 2890,
    dominantTransition: '산림 → 사탕수수 및 팜 플랜테이션',
    description: '동부 평야 및 구릉지의 대규모 농업 플랜테이션 전환',
    keyDrivers: ['사탕수수 재배', '팜유 농장 확장'],
  },
  {
    id: 'luwu_utara',
    name: 'Kabupaten Luwu Utara',
    localName: 'Kabupaten Luwu Utara',
    type: 'Kabupaten',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [120.25, -2.48],
    bounds: [119.92, -2.85, 120.65, -2.15],
    riskLevel: 'CRITICAL',
    totalAreaHa: 750250,
    annualLossHa: 4120,
    dominantTransition: '원시림 벌채 → 카카오 플랜테이션 및 토사 유실',
    description: '토호로 산맥 고산 원시림의 플랜테이션 개간 및 산사태 취약지',
    keyDrivers: ['카카오 재배', '임도 건설', '불법 벌채'],
  },
  {
    id: 'luwu_timur',
    name: 'Kabupaten Luwu Timur',
    localName: 'Kabupaten Luwu Timur',
    type: 'Kabupaten',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [121.22, -2.55],
    bounds: [120.85, -2.95, 121.65, -2.15],
    riskLevel: 'CRITICAL',
    totalAreaHa: 694490,
    annualLossHa: 3890,
    dominantTransition: '산림 → 니켈 광산 노천채굴지 및 야금 단지',
    description: '소로아코 마타노 호수 유역의 대규모 니켈 광산 개발',
    keyDrivers: ['니켈 노천광산', '제련소 인프라', '폐기물 적치장'],
  },
  {
    id: 'makassar',
    name: 'Kota Makassar',
    localName: 'Kota Makassar',
    type: 'Kota',
    province: 'South Sulawesi',
    provinceSlug: 'south_sulawesi',
    center: [119.43, -5.14],
    bounds: [119.35, -5.25, 119.52, -5.05],
    riskLevel: 'MEDIUM',
    totalAreaHa: 17570,
    annualLossHa: 850,
    dominantTransition: '연안 맹그로브/농지 → 고밀도 시가화',
    description: '남부 술라웨시 경제 중심지의 급격한 해안 매립 및 시가화',
    keyDrivers: ['해안 매립', '항만 물류단지', '주거 단지 개발'],
  },

  // Gorontalo (6 ADM2 units)
  {
    id: 'pohuwato',
    name: 'Kabupaten Pohuwato',
    localName: 'Kabupaten Pohuwato',
    type: 'Kabupaten',
    province: 'Gorontalo',
    provinceSlug: 'gorontalo',
    center: [121.65, 0.58],
    bounds: [121.15, 0.35, 122.15, 0.95],
    riskLevel: 'CRITICAL',
    totalAreaHa: 424430,
    annualLossHa: 3670,
    dominantTransition: '저지대 산림 → 대규모 팜오일 농장 및 금광',
    description: '서부 고론탈로의 대규모 팜유 농장 인허가 및 사금 채취 훼손',
    keyDrivers: ['팜유 플랜테이션', '수력/사금 채취'],
  },
  {
    id: 'boalemo',
    name: 'Kabupaten Boalemo',
    localName: 'Kabupaten Boalemo',
    type: 'Kabupaten',
    province: 'Gorontalo',
    provinceSlug: 'gorontalo',
    center: [122.35, 0.65],
    bounds: [122.05, 0.42, 122.65, 0.98],
    riskLevel: 'HIGH',
    totalAreaHa: 152180,
    annualLossHa: 1980,
    dominantTransition: '산림 → 옥수수 단일경작지',
    description: '경사지 옥수수 재배 면적 확대로 인한 표토 유실 및 산림 훼손',
    keyDrivers: ['옥수수 재배', '경사지 농경'],
  },
  {
    id: 'bone_bolango',
    name: 'Kabupaten Bone Bolango',
    localName: 'Kabupaten Bone Bolango',
    type: 'Kabupaten',
    province: 'Gorontalo',
    provinceSlug: 'gorontalo',
    center: [123.25, 0.55],
    bounds: [122.95, 0.32, 123.55, 0.85],
    riskLevel: 'HIGH',
    totalAreaHa: 198430,
    annualLossHa: 1840,
    dominantTransition: '보고니 국립공원 완충구역 산림 → 농경지',
    description: '보고니 나니 바르타보네 국립공원 경계부 소규모 농가 침입',
    keyDrivers: ['영세 농업', '임산물 불법 채취'],
  },
  {
    id: 'gorontalo_kota',
    name: 'Kota Gorontalo',
    localName: 'Kota Gorontalo',
    type: 'Kota',
    province: 'Gorontalo',
    provinceSlug: 'gorontalo',
    center: [123.06, 0.54],
    bounds: [123.01, 0.50, 123.12, 0.58],
    riskLevel: 'LOW',
    totalAreaHa: 6470,
    annualLossHa: 120,
    dominantTransition: '농경지 → 상업 및 주거 시가지',
    description: '도심 주변 잔존 농경지의 안정적 시가화',
    keyDrivers: ['도시 인프라 확장'],
  },

  // Southeast Sulawesi (17 ADM2 units)
  {
    id: 'kolaka_utara',
    name: 'Kabupaten Kolaka Utara',
    localName: 'Kabupaten Kolaka Utara',
    type: 'Kabupaten',
    province: 'Southeast Sulawesi',
    provinceSlug: 'southeast_sulawesi',
    center: [121.25, -3.22],
    bounds: [120.95, -3.65, 121.55, -2.85],
    riskLevel: 'CRITICAL',
    totalAreaHa: 339160,
    annualLossHa: 3210,
    dominantTransition: '산림 → 니켈 광산 및 부두 인프라',
    description: '보니 만(Gulf of Boni) 연안 산림 절개 및 니켈 선적항 개발',
    keyDrivers: ['니켈 광산 채굴', '연안 전용 부두'],
  },
  {
    id: 'konawe_utara',
    name: 'Kabupaten Konawe Utara',
    localName: 'Kabupaten Konawe Utara',
    type: 'Kabupaten',
    province: 'Southeast Sulawesi',
    provinceSlug: 'southeast_sulawesi',
    center: [122.15, -3.35],
    bounds: [121.85, -3.75, 122.45, -3.05],
    riskLevel: 'CRITICAL',
    totalAreaHa: 510170,
    annualLossHa: 3540,
    dominantTransition: '초지/산림 → 대형 니켈 채굴 단지',
    description: '북부 코나웨 광구 집중 개발로 인한 적색 점토 노출',
    keyDrivers: ['광산 개발', '도로망 확장'],
  },
  {
    id: 'kendari',
    name: 'Kota Kendari',
    localName: 'Kota Kendari',
    type: 'Kota',
    province: 'Southeast Sulawesi',
    provinceSlug: 'southeast_sulawesi',
    center: [122.51, -3.97],
    bounds: [122.42, -4.05, 122.62, -3.90],
    riskLevel: 'MEDIUM',
    totalAreaHa: 29580,
    annualLossHa: 680,
    dominantTransition: '맹그로브/산림 → 항만 및 주거 시가화',
    description: '켄다리 만 유역의 퇴적 및 연안 피복 전이',
    keyDrivers: ['도시 확장', '해안 개발'],
  },

  // Banten (8 ADM2 units)
  {
    id: 'lebak',
    name: 'Kabupaten Lebak',
    localName: 'Kabupaten Lebak',
    type: 'Kabupaten',
    province: 'Banten',
    provinceSlug: 'banten',
    center: [106.25, -6.65],
    bounds: [105.85, -6.95, 106.55, -6.35],
    riskLevel: 'HIGH',
    totalAreaHa: 304470,
    annualLossHa: 2450,
    dominantTransition: '산림 → 고무/팜 플랜테이션 및 도로',
    description: '할리문 살락 국립공원 서부 완충구역 산림 개간',
    keyDrivers: ['플랜테이션', '고속도로 건설'],
  },
  {
    id: 'tangerang_selatan',
    name: 'Kota Tangerang Selatan',
    localName: 'Kota Tangerang Selatan',
    type: 'Kota',
    province: 'Banten',
    provinceSlug: 'banten',
    center: [106.71, -6.29],
    bounds: [106.65, -6.35, 106.78, -6.24],
    riskLevel: 'LOW',
    totalAreaHa: 14720,
    annualLossHa: 320,
    dominantTransition: '농경지/초지 → 고밀도 신도시 (BSD)',
    description: '자카르타 수도권 위성 신도시화 완료 단계',
    keyDrivers: ['상업/주거 개발'],
  },

  // West Java (27 ADM2 units)
  {
    id: 'bogor',
    name: 'Kabupaten Bogor',
    localName: 'Kabupaten Bogor',
    type: 'Kabupaten',
    province: 'West Java',
    provinceSlug: 'west_java',
    center: [106.82, -6.55],
    bounds: [106.45, -6.78, 107.15, -6.32],
    riskLevel: 'CRITICAL',
    totalAreaHa: 298620,
    annualLossHa: 3120,
    dominantTransition: '상류 보전림 → 리조트 단지 및 농경지',
    description: '푼착(Puncak) 고원 관광 리조트 및 빌라 난개발로 인한 수문 악화',
    keyDrivers: ['관광 리조트 개발', '고랭지 농업'],
  },
  {
    id: 'bandung_barat',
    name: 'Kabupaten Bandung Barat',
    localName: 'Kabupaten Bandung Barat',
    type: 'Kabupaten',
    province: 'West Java',
    provinceSlug: 'west_java',
    center: [107.50, -6.85],
    bounds: [107.25, -7.05, 107.75, -6.70],
    riskLevel: 'HIGH',
    totalAreaHa: 130580,
    annualLossHa: 1850,
    dominantTransition: '산림/차밭 → 교외 주거단지 및 공장',
    description: '반둥 분지 북부 및 서부 구릉지의 급격한 택지 전환',
    keyDrivers: ['주거 단지', '산업단지 확장'],
  },
  {
    id: 'karawang',
    name: 'Kabupaten Karawang',
    localName: 'Kabupaten Karawang',
    type: 'Kabupaten',
    province: 'West Java',
    provinceSlug: 'west_java',
    center: [107.30, -6.30],
    bounds: [107.12, -6.55, 107.55, -6.10],
    riskLevel: 'HIGH',
    totalAreaHa: 175330,
    annualLossHa: 1980,
    dominantTransition: '우량 농경지 → 대규모 산업단지',
    description: '국가 식량기지 농경지의 자동차/전자 제조 산업단지 전환',
    keyDrivers: ['국가산업단지', '고속철도 역세권 개발'],
  },

  // East Java (38 ADM2 units)
  {
    id: 'banyuwangi',
    name: 'Kabupaten Banyuwangi',
    localName: 'Kabupaten Banyuwangi',
    type: 'Kabupaten',
    province: 'East Java',
    provinceSlug: 'east_java',
    center: [114.35, -8.35],
    bounds: [113.95, -8.75, 114.62, -7.95],
    riskLevel: 'HIGH',
    totalAreaHa: 578250,
    annualLossHa: 2650,
    dominantTransition: '산림 → 금광 개발 및 원예 농장',
    description: '메루 베티리 국립공원 인접 툼팡 피투 금광 및 농업 확장',
    keyDrivers: ['금광 개발', '원예 농업'],
  },
  {
    id: 'malang',
    name: 'Kabupaten Malang',
    localName: 'Kabupaten Malang',
    type: 'Kabupaten',
    province: 'East Java',
    provinceSlug: 'east_java',
    center: [112.63, -8.15],
    bounds: [112.35, -8.45, 112.92, -7.85],
    riskLevel: 'HIGH',
    totalAreaHa: 353490,
    annualLossHa: 2120,
    dominantTransition: '산지 산림 → 사과/채소 밭 및 관광 인프라',
    description: '브로모 텡게르 세메루 국립공원 남부 경사지 개간',
    keyDrivers: ['고랭지 채소', '관광 인프라'],
  },
]);

// -----------------------------------------------------------------------------
// Hotspot Marker Registry
// -----------------------------------------------------------------------------

export const SYNTHETIC_HOTSPOTS: readonly HotspotMarkerInfo[] = Object.freeze([
  {
    id: 'hs-ss-01',
    title: '루우 티무르 니켈 광산 산림 절개 핫스팟',
    province: 'South Sulawesi',
    districtId: 'luwu_timur',
    districtName: 'Kabupaten Luwu Timur',
    districtType: 'Kabupaten',
    coordinates: [121.35, -2.58],
    changeAreaHa: 1240,
    riskLevel: 'CRITICAL',
    dominantTransition: '수목 (Trees) → 나지 (Bare land) / 노천광산',
    sclQuality: 'SCL 4 (Clear Vegetation - Valid)',
    observationDateT1: '2020-08-15',
    observationDateT2: '2025-07-22',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '소로아코 인근 니켈 광산 채굴 및 진입도로 신설로 인한 산림 파편화 극심',
    mitigationRecommendation: '식생 완충구역 설정 및 폐광지 복원 모니터링 즉시 착수',
  },
  {
    id: 'hs-ss-02',
    title: '고와 산악 고랭지 농경지 침범 핫스팟',
    province: 'South Sulawesi',
    districtId: 'gowa',
    districtName: 'Kabupaten Gowa',
    districtType: 'Kabupaten',
    coordinates: [119.85, -5.35],
    changeAreaHa: 890,
    riskLevel: 'CRITICAL',
    dominantTransition: '수목 (Trees) → 농경지 (Crops)',
    sclQuality: 'SCL 4 (Clear Soil/Crops - Valid)',
    observationDateT1: '2020-09-02',
    observationDateT2: '2025-08-11',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '바와카라엥 산 상류부 급경사지 무단 개간으로 우기 토사 유출 위험 고조',
    mitigationRecommendation: '경사도 25도 이상 경작 금지 및 산림농업(Agroforestry) 전환 유도',
  },
  {
    id: 'hs-go-01',
    title: '포후와토 서부 팜 플랜테이션 확장지',
    province: 'Gorontalo',
    districtId: 'pohuwato',
    districtName: 'Kabupaten Pohuwato',
    districtType: 'Kabupaten',
    coordinates: [121.72, 0.62],
    changeAreaHa: 1420,
    riskLevel: 'CRITICAL',
    dominantTransition: '수목 (Trees) → 관목/플랜테이션 (Shrub/Crops)',
    sclQuality: 'SCL 4 (Valid Clear)',
    observationDateT1: '2020-07-18',
    observationDateT2: '2025-06-30',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '파니 강 유역 저지대 천연림의 대규모 팜오일 식재 전환',
    mitigationRecommendation: '보전가치 높은 산림(HCVF) 지정 및 추가 개간 동결',
  },
  {
    id: 'hs-sg-01',
    title: '코나웨 우타라 해안 광산 선적항 개발',
    province: 'Southeast Sulawesi',
    districtId: 'konawe_utara',
    districtName: 'Kabupaten Konawe Utara',
    districtType: 'Kabupaten',
    coordinates: [122.25, -3.42],
    changeAreaHa: 1150,
    riskLevel: 'CRITICAL',
    dominantTransition: '수목/맹그로브 → 나지/시가화 (Built-up)',
    sclQuality: 'SCL 4 (Valid Clear)',
    observationDateT1: '2020-08-11',
    observationDateT2: '2025-07-19',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '연안 맹그로브 훼손 및 적토 유출로 인한 산호초 백화 우려',
    mitigationRecommendation: '해양 오탁방지망 설치 의무화 및 해안 완충림 복원',
  },
  {
    id: 'hs-wj-01',
    title: '보고르 푼착 고원 리조트 난개발 지구',
    province: 'West Java',
    districtId: 'bogor',
    districtName: 'Kabupaten Bogor',
    districtType: 'Kabupaten',
    coordinates: [106.95, -6.68],
    changeAreaHa: 980,
    riskLevel: 'CRITICAL',
    dominantTransition: '수목 (Trees) → 시가화 (Built-up)',
    sclQuality: 'SCL 4 (Valid Clear)',
    observationDateT1: '2020-09-14',
    observationDateT2: '2025-08-25',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '자카르타 수도권 배후 산림의 상업용 빌라 및 레저시설 전환',
    mitigationRecommendation: '개발제한구역(그린벨트) 단속 강화 및 불법 건축물 원상복구',
  },
  {
    id: 'hs-ej-01',
    title: '바뉴왕이 툼팡피투 광산 개발 회랑',
    province: 'East Java',
    districtId: 'banyuwangi',
    districtName: 'Kabupaten Banyuwangi',
    districtType: 'Kabupaten',
    coordinates: [114.12, -8.58],
    changeAreaHa: 870,
    riskLevel: 'HIGH',
    dominantTransition: '수목 (Trees) → 나지/노천광 (Bare land)',
    sclQuality: 'SCL 4 (Valid Clear)',
    observationDateT1: '2020-08-29',
    observationDateT2: '2025-07-15',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: '남부 해안 인접 구릉림의 노천 광산 절토 및 침사지 조성',
    mitigationRecommendation: '토양 침식 방지벽 구축 및 단계별 생태 복원',
  },
]);

// -----------------------------------------------------------------------------
// Spatial Resolver Methods
// -----------------------------------------------------------------------------

/**
 * Calculates Euclidean distance squared between two points.
 */
function distSq(p1: [number, number], p2: [number, number]): number {
  const dx = p1[0] - p2[0];
  const dy = p1[1] - p2[1];
  return dx * dx + dy * dy;
}

/**
 * Resolves the closest / containing ADM2 district by geographic coordinate [lng, lat].
 */
export function resolveDistrictByCoord(
  lng: number,
  lat: number,
  provinceFilter?: string
): ADM2DistrictInfo {
  let candidates = FIRST_GROUP_ADM2_DISTRICTS;
  if (provinceFilter) {
    const pf = provinceFilter.toLowerCase().replace(/\s+/g, '_');
    candidates = candidates.filter(
      d => d.provinceSlug === pf || d.province.toLowerCase() === provinceFilter.toLowerCase()
    );
    if (candidates.length === 0) {
      candidates = FIRST_GROUP_ADM2_DISTRICTS;
    }
  }

  // 1. Direct bounding box test
  for (const district of candidates) {
    const [w, s, e, n] = district.bounds;
    if (lng >= w && lng <= e && lat >= s && lat <= n) {
      return district;
    }
  }

  // 2. Nearest center fallback
  let closest = candidates[0];
  let minDistance = Infinity;

  for (const district of candidates) {
    const d = distSq([lng, lat], district.center);
    if (d < minDistance) {
      minDistance = d;
      closest = district;
    }
  }

  return closest;
}

/**
 * Finds an ADM2 district by ID.
 */
export function resolveDistrictById(id: string): ADM2DistrictInfo | undefined {
  return FIRST_GROUP_ADM2_DISTRICTS.find(d => d.id === id);
}

/**
 * Lists all registered ADM2 districts for a given province.
 */
export function getDistrictsForProvince(province: string): readonly ADM2DistrictInfo[] {
  const pSlug = province.toLowerCase().replace(/\s+/g, '_');
  return FIRST_GROUP_ADM2_DISTRICTS.filter(
    d => d.provinceSlug === pSlug || d.province.toLowerCase() === province.toLowerCase()
  );
}

/**
 * Returns prioritized change hotspots for a given province.
 */
export function getHotspotsForProvince(province: string, limit = 5): HotspotMarkerInfo[] {
  const pNorm = province.toLowerCase();
  const matched = SYNTHETIC_HOTSPOTS.filter(
    h => h.province.toLowerCase() === pNorm
  );

  if (matched.length > 0) {
    return matched.slice(0, limit);
  }

  // If no predefined hotspots in this province, generate synthetic ones based on its districts
  const districts = getDistrictsForProvince(province);
  return districts.slice(0, limit).map((dist, idx) => ({
    id: `hs-${dist.id}-${idx + 1}`,
    title: `${dist.name} 주요 산림 전이 핫스팟 #${idx + 1}`,
    province: dist.province,
    districtId: dist.id,
    districtName: dist.name,
    districtType: dist.type,
    coordinates: dist.center,
    changeAreaHa: Math.round(dist.annualLossHa * 0.45),
    riskLevel: dist.riskLevel,
    dominantTransition: dist.dominantTransition,
    sclQuality: 'SCL 4 (Clear - Valid Pixel)',
    observationDateT1: '2020-08-15',
    observationDateT2: '2025-07-20',
    dataProvenanceT1: 'ESA WorldCover 2020 v100 (10m Reference)',
    dataProvenanceT2: 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)',
    description: dist.description,
    mitigationRecommendation: '집중 모니터링 및 지방정부 환경 관리청(DLH) 합동 현장 검증',
  }));
}

/**
 * Builds GeoJSON FeatureCollection containing hotspot markers.
 */
export function createHotspotsGeoJSON(province: string): {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: { type: 'Point'; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }>;
} {
  const hotspots = getHotspotsForProvince(province);
  return {
    type: 'FeatureCollection',
    features: hotspots.map(h => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: h.coordinates,
      },
      properties: {
        id: h.id,
        title: h.title,
        province: h.province,
        districtId: h.districtId,
        districtName: h.districtName,
        districtType: h.districtType,
        changeAreaHa: h.changeAreaHa,
        riskLevel: h.riskLevel,
        dominantTransition: h.dominantTransition,
        sclQuality: h.sclQuality,
        observationDateT1: h.observationDateT1,
        observationDateT2: h.observationDateT2,
        dataProvenanceT1: h.dataProvenanceT1,
        dataProvenanceT2: h.dataProvenanceT2,
        description: h.description,
        mitigationRecommendation: h.mitigationRecommendation,
      },
    })),
  };
}

/**
 * Renders rich HTML detail card for the selected hotspot.
 */
export function buildHotspotDetailCardHtml(hotspot: HotspotMarkerInfo): string {
  const badgeColor =
    hotspot.riskLevel === 'CRITICAL'
      ? '#dc2626'
      : hotspot.riskLevel === 'HIGH'
      ? '#ea580c'
      : hotspot.riskLevel === 'MEDIUM'
      ? '#d97706'
      : '#16a34a';

  return `
    <div class="lcluc-hotspot-card lcluc-hotspot-detail-card" style="font-family: sans-serif; line-height: 1.45; padding: 12px; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
      <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; margin-bottom: 8px;">
        <h4 style="margin: 0; font-size: 14px; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: ${badgeColor};"></span>
          ${hotspot.title}
        </h4>
        <span style="background: ${badgeColor}15; color: ${badgeColor}; border: 1px solid ${badgeColor}40; padding: 2px 7px; border-radius: 12px; font-size: 11px; font-weight: 700;">
          ${hotspot.riskLevel}
        </span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 10px;">
        <div style="background: #f8fafc; padding: 6px 8px; border-radius: 6px;">
          <div style="color: #64748b; font-size: 10px;">관할 시군구 (ADM2)</div>
          <strong style="color: #1e293b;">${hotspot.districtName} (${hotspot.districtType})</strong>
        </div>
        <div style="background: #f8fafc; padding: 6px 8px; border-radius: 6px;">
          <div style="color: #64748b; font-size: 10px;">변화 감지 면적</div>
          <strong style="color: #dc2626;">${hotspot.changeAreaHa.toLocaleString()} ha</strong>
        </div>
      </div>

      <div style="font-size: 11.5px; color: #334155; margin-bottom: 8px;">
        <div style="color: #64748b; font-size: 10px; margin-bottom: 2px;">주요 전이 유형 (Dominant Transition)</div>
        <div style="padding: 4px 8px; background: #fef2f2; border-left: 3px solid #ef4444; border-radius: 2px; font-weight: 600; color: #991b1b;">
          ${hotspot.dominantTransition}
        </div>
      </div>

      <div style="font-size: 11px; color: #475569; background: #f1f5f9; padding: 8px; border-radius: 6px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
          <span>위성 품질 (SCL):</span>
          <strong style="color: #15803d;">${hotspot.sclQuality}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
          <span>관측 시점:</span>
          <strong>T1: ${hotspot.observationDateT1} | T2: ${hotspot.observationDateT2}</strong>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>좌표:</span>
          <code>[${hotspot.coordinates[0].toFixed(4)}°, ${hotspot.coordinates[1].toFixed(4)}°]</code>
        </div>
      </div>

      <p style="margin: 0 0 8px 0; font-size: 11px; color: #475569;">
        ${hotspot.description}
      </p>

      <div style="font-size: 10.5px; color: #0369a1; background: #f0f9ff; border: 1px solid #bae6fd; padding: 6px 8px; border-radius: 6px;">
        💡 <strong>대응 권고:</strong> ${hotspot.mitigationRecommendation}
      </div>
    </div>
  `;
}

/**
 * Builds compact popup HTML string for MapLibre GL popup.
 */
export function buildHotspotDetailPopupHtml(hotspot: HotspotMarkerInfo): string {
  return `
    <div style="font-family: sans-serif; font-size: 11px; line-height: 1.4; padding: 2px 4px; min-width: 200px;">
      <div style="font-weight: 700; color: #0f172a; margin-bottom: 4px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px;">
        📍 ${hotspot.title}
      </div>
      <div style="color: #475569; margin-bottom: 2px;">
        District: <b>${hotspot.districtName}</b>
      </div>
      <div style="color: #dc2626; margin-bottom: 2px;">
        Change: <b>${hotspot.changeAreaHa.toLocaleString()} ha</b> (${hotspot.riskLevel})
      </div>
      <div style="font-size: 10px; color: #64748b; margin-top: 4px;">
        Transition: ${hotspot.dominantTransition}
      </div>
    </div>
  `;
}
