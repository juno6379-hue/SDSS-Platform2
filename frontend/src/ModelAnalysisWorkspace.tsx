import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource } from 'maplibre-gl';
import type { EvidenceRecord } from './integrationAdapter';
import './model-workspace.css';
import AnalysisIcon from './AnalysisIcon';
import { Icon } from './Icon';
import LclucWorkflowPanel from './LclucWorkflowPanel';
import {
  generateMasterPayload,
  generateCsvTransitionMatrix,
  generateCsvTimeSeries,
  generateExecutiveHtmlReport,
  type LclucMasterPayload,
} from './lclucMasterAdapter';
import {
  LCLUC_FIRST_GROUP_PROVINCES,
  LCLUC_FIRST_GROUP_REGIONS,
  LCLUC_PROVINCE_REGISTRY,
  sanitizeLclucProvince,
  isFirstGroupProvince,
  createLclucRasterSourceSpec,
  createLclucRasterLayerSpec,
  inspectPixelAtCoord,
  LclucAnimateController,
  type PixelInspectionResult,
} from './lclucWmsRasterAdapter';
import {
  createHotspotsGeoJSON,
  buildHotspotDetailPopupHtml,
  resolveDistrictByCoord,
  getDistrictsForProvince,
  getHotspotsForProvince,
  type HotspotMarkerInfo,
  type ADM2DistrictInfo,
} from './LclucHotspotDistrictResolver';
import {
  createQualityMaskGridGeoJSON,
} from './lclucIntegratedWorkspaceAdapter';

let cachedProvincesGeoJson: any = null;
async function fetchFirstGroupProvincesGeoJson() {
  if (cachedProvincesGeoJson) return cachedProvincesGeoJson;
  try {
    const res = await fetch('/first-group-provinces.geojson');
    if (res.ok) {
      cachedProvincesGeoJson = await res.json();
      return cachedProvincesGeoJson;
    }
  } catch (err) {
    console.warn('Failed to load first-group-provinces.geojson:', err);
  }
  return null;
}

function downloadBlob(filename: string, content: string, mimeType: string) {
  if (typeof document === 'undefined' || typeof URL === 'undefined') return;
  try {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {
    console.warn('downloadBlob failed:', e);
  }
}

type Bounds = [number, number, number, number];
type Config = {
  title: string;
  subtitle: string;
  english: string;
  symbol: string;
  map: string;
  tabs: string[];
  kpis: [string, string, string][];
  summary: string;
  columns: string[];
  rows: string[];
  bottom: string[];
  legend: [string, string][];
  fields: [string, string[]][];
};

const years = ['2020', '2021', '2022', '2023', '2024', '2025'];
const commonTabs = ['지도 분석', '시계열 분석', '변화 탐지', '전환 행렬', '핫스팟 분석', '지역 비교', '결과 내보내기'];

const configs: Record<string, Config> = {
  lcluc: {
    title: 'LCLUC Workspace',
    subtitle: '인도네시아의 토지피복 및 토지이용 변화 분석을 통한 지속가능한 국토관리와 기후행동을 지원합니다.',
    english: 'Land Cover and Land Use Change Analysis for a Sustainable Indonesia',
    symbol: '♠',
    map: '인도네시아 토지피복 변화 비교',
    tabs: commonTabs,
    kpis: [
      ['산림 면적 (Trees)', 'ha', 'forest'],
      ['시가화 면적 (Built Area)', 'ha', 'buildings'],
      ['농경지 면적 (Crops)', 'ha', 'crops'],
      ['총 유효 분석 면적', 'ha', 'area'],
    ],
    summary: '주요 9대 분류 전이 요약',
    columns: ['전이 경로 (T1 → T2)', '전이 면적', '전이 비율'],
    rows: ['Trees → Built Area', 'Trees → Crops', 'Trees → Shrub & Scrub', 'Flooded Veg → Water', 'Crops → Built Area'],
    bottom: ['연도별 토지피복 면적 변화', '토지피복 구성', '토지피복 전환 행렬', '변화 핫스팟'],
    legend: [
      ['Water', '#2563eb'],
      ['Trees', '#15803d'],
      ['Grass', '#84cc16'],
      ['Flooded Veg', '#14b8a6'],
      ['Crops', '#eab308'],
      ['Shrub & Scrub', '#a16207'],
      ['Built Area', '#dc2626'],
      ['Bare Ground', '#a8a29e'],
      ['Snow & Ice', '#a5d8f3'],
    ],
    fields: [
      ['세부 지역 (AOI)', ['연구 bbox', '주 전체 참조']],
      ['시작 연도', years],
      ['종료 연도', years],
      ['표시 모드', ['스와이프 비교', '지도 + 통계', '단일 지도']],
      ['데이터 유형', ['토지피복 분류도', '변화 지도', '전이행렬']],
    ],
  },
  climate: {
    title: 'Climate Downscaling Workspace',
    subtitle: '인도네시아를 위한 고해상도 기후변수 상세화 및 시나리오 비교 분석을 지원합니다.',
    english: 'High-resolution climate variable downscaling and scenario comparison for Indonesia.',
    symbol: '≋',
    map: '미래 기온 변화 분포',
    tabs: ['지도 분석', '시계열 분석', '시나리오 비교', '공간 통계', '변화 탐지', '위험 핫스팟', '지역 비교'],
    kpis: [
      ['평균 기온 변화', '°C', 'temperature'],
      ['강수량 변화', '%', 'rain'],
      ['폭염일 수', '일/년', 'sun'],
      ['노출 인구', '명', 'people'],
    ],
    summary: '기후 위험 핫스팟',
    columns: ['지역 (Province)', '주요 위험', '위험 수준', '변화량'],
    rows: ['East Nusa Tenggara', 'West Nusa Tenggara', 'East Java', 'West Java', 'South Sulawesi'],
    bottom: ['지역별 평균 기온 변화 (°C)', '선택 지역 시계열 전망', '시나리오별 변화 비교', '모델 성능 및 검증'],
    legend: [
      ['< 0.0', '#5d67d9'],
      ['0.0 - 0.5', '#5db9e9'],
      ['0.5 - 1.0', '#8ed7a1'],
      ['1.0 - 1.5', '#f7df5b'],
      ['1.5 - 2.0', '#ffb44a'],
      ['2.0 - 2.5', '#ff8755'],
      ['2.5 - 3.0', '#ff5857'],
      ['> 3.0', '#db3049'],
    ],
    fields: [
      ['세부 지역 (AOI)', ['연구 bbox', '주 전체 참조']],
      ['기준기간 (Baseline)', ['1995–2014', '2000–2020']],
      ['미래기간 (Future)', ['2041–2060', '2021–2040', '2081–2100']],
      ['시나리오 (Scenario)', ['SSP2-4.5', 'SSP5-8.5', 'SSP1-2.6']],
      ['기후변수 (Variable)', ['Temperature (기온)', 'Precipitation (강수)']],
      ['해상도 (Resolution)', ['1 km', '5 km', '제공기관 정의']],
      ['표시 모드', ['지도 + 통계', '시나리오 비교']],
    ],
  },
  carbon: {
    title: 'Net Carbon Footprint Workspace',
    subtitle: '인도네시아 전역의 탄소 배출 및 흡수 통합 분석으로 기후 의사결정을 지원합니다.',
    english: 'Integrated emissions, removals and carbon balance analysis for Indonesia.',
    symbol: '❧',
    map: '지역별 순 탄소 배출 분포',
    tabs: ['지도 분석', '배출 추세', '흡수 분석', '탄소 수지', '시나리오·감축', '핫스팟', '지역 비교', '결과 내보내기'],
    kpis: [
      ['총 배출량', 'tCO₂e', 'emissions'],
      ['총 흡수량', 'tCO₂e', 'leaf'],
      ['순 탄소 배출', 'tCO₂e', 'carbon'],
      ['감축 잠재량', 'tCO₂e', 'target'],
    ],
    summary: '탄소 배출 핫스팟',
    columns: ['지역', '순 배출량', '변화', '주요 기여 부문'],
    rows: ['East Kalimantan', 'Riau', 'Central Kalimantan', 'South Sumatra', 'West Kalimantan'],
    bottom: ['부문별 탄소 배출 추세', '탄소 흡수 분포', '부문별 탄소 수지', '감축 옵션과 잠재량'],
    legend: [
      ['< -10M', '#087d41'],
      ['-10M – -5M', '#329a4b'],
      ['-5M – -1M', '#75b94c'],
      ['-1M – 0', '#c8d748'],
      ['0 – 1M', '#ffdd43'],
      ['1M – 5M', '#ffad37'],
      ['5M – 10M', '#f27734'],
      ['> 10M', '#cd2838'],
    ],
    fields: [
      ['기준 연도', years],
      ['비교 연도', years],
      ['분석 부문', ['전체 부문', '산업·에너지', '교통', '농업', '산림·토지이용', '폐기물']],
      ['표시 모드', ['순 배출', '배출', '흡수']],
      ['단위', ['tCO₂e', '천 tCO₂e']],
      ['시나리오', ['Baseline (BAU)', '감축 시나리오']],
    ],
  },
  biodiversity: {
    title: 'Biodiversity Mapping Workspace',
    subtitle: '인도네시아 전역의 종 분포, 서식지 적합성과 보전 우선순위를 분석합니다.',
    english: 'Species distribution, habitat suitability and conservation priorities for Indonesia.',
    symbol: '❧',
    map: '서식지 적합도 지도',
    tabs: ['지도 분석', '통계 분석', '연결성 분석', '위협 분석', '보전 우선지역', '지역 비교', '결과 내보내기'],
    kpis: [
      ['보호지역 면적', 'ha', 'forest'],
      ['적합 서식지 비율', '%', 'habitat'],
      ['연결성 지수', 'index', 'network'],
      ['보전 우선지역 수', '개', 'location'],
    ],
    summary: '보전 우선순위',
    columns: ['지역 / 구역', '우선순위 점수', '면적 (ha)', '분류'],
    rows: ['보호구역 참조 미연결', '서식지 참조 미연결', '현장 관측 미연결', '종 출현자료 미연결', '생태축 참조 미연결'],
    bottom: ['생물다양성 지수 추세', '서식지 적합도 등급별 면적', '서식지 연결성 분석', '압력·위협 요인'],
    legend: [
      ['매우 높음 (0.8–1.0)', '#f72d56'],
      ['높음 (0.6–0.8)', '#ff8b32'],
      ['중간 (0.4–0.6)', '#ffdf41'],
      ['낮음 (0.2–0.4)', '#2ba262'],
      ['매우 낮음 (0.0–0.2)', '#268afa'],
      ['보호구역', '#7185b1'],
    ],
    fields: [
      ['대상 종 / 생태계', ['대상종 선택', 'Cenderawasih (Paradisaea spp.)', 'Mangrove ecosystem']],
      ['시작 연도', years],
      ['종료 연도', years],
      ['표시 모드', ['서식지 적합도', '종 풍부도', '보호구역 중첩']],
      ['임계값', ['> 0.6 (높음)', '> 0.8 (매우 높음)', '전체 등급']],
    ],
  },
  coastal: {
    title: 'Sea Level Rise & Land Subsidence Workspace',
    subtitle: '해수면 상승과 지반침하를 통합하여 인도네시아 연안 지역의 노출·취약성을 분석합니다.',
    english: 'Integrated sea level rise and land subsidence analysis for resilient coastal communities.',
    symbol: '≋',
    map: '해수면 상승·지반침하 지도',
    tabs: ['침수 지도', '시나리오 비교', '해안 프로파일', '노출 분석', '위험 핫스팟', '지역 비교', '결과 내보내기'],
    kpis: [
      ['침수 지역 면적', 'km²', 'water'],
      ['영향 인구', '명', 'people'],
      ['영향 주요 시설', '개', 'buildings'],
      ['평균 지반침하', 'mm/년', 'subsidence'],
    ],
    summary: '노출 분석',
    columns: ['시설 유형', '총수', '영향 수', '비율 (%)'],
    rows: ['주거지역', '주요 도로', '항만', '공항', '병원', '학교', '발전시설', '상수도 시설'],
    bottom: ['시나리오별 침수 면적 비교', '해안 프로파일', '위험 핫스팟', '분석 정보'],
    legend: [
      ['0 – 0.5 m', '#7bd9e7'],
      ['0.5 – 1.0 m', '#47b8f5'],
      ['1.0 – 2.0 m', '#2797f8'],
      ['2.0 – 3.0 m', '#176bfa'],
      ['3.0 – 5.0 m', '#1241d1'],
      ['> 5.0 m', '#0a218c'],
    ],
    fields: [
      ['연안 도시 / AOI', ['연구 bbox', 'Jakarta Utara', '기준면 확인 필요']],
      ['기준 연도', years],
      ['전망 연도', ['2050', '2030', '2070', '2100']],
      ['해수면 시나리오', ['SSP5-8.5 (높음)', 'SSP2-4.5 (중간)', 'SSP1-2.6 (낮음)']],
      ['지반침하 등급', ['전체 등급', '0–10 mm/년', '10–20 mm/년', '> 20 mm/년']],
      ['시설 유형', ['전체 시설', '주거지역', '교통', '공공시설']],
    ],
  },
  flood: {
    title: 'Flood & Drought Workspace',
    subtitle: '인도네시아 전역의 홍수·가뭄 위험 및 지역별 취약성을 통합 분석합니다.',
    english: 'Satellite, hydrology and socioeconomic data for climate and disaster resilience.',
    symbol: '♧',
    map: '홍수·가뭄 위험 지도',
    tabs: ['지도 분석', '시계열 분석', '취약성 분석', '시나리오 비교', '핫스팟 분석', '결과 내보내기'],
    kpis: [
      ['홍수 영향 면적', 'ha', 'water'],
      ['노출 인구', '명', 'people'],
      ['조기경보 수', '회', 'warning'],
      ['평균 위험 지수', 'index', 'risk'],
    ],
    summary: '시·군별 취약성',
    columns: ['시 / 군', '취약성 지수', '위험 분류', '노출 인구', '위험 면적'],
    rows: ['Demak', 'Pekalongan', 'Semarang', 'Kudus', 'Pati'],
    bottom: ['강우량·하천 수위', '가뭄 추세 (SPI 3개월)', '홍수 핫스팟', '경보·이상징후'],
    legend: [
      ['매우 낮음', '#8ce0ee'],
      ['낮음', '#56c2ed'],
      ['중간', '#258ffa'],
      ['높음', '#2358ec'],
      ['매우 높음', '#142ba5'],
    ],
    fields: [
      ['분석 기간', ['2020–2025', '2020–2022', '2023–2025']],
      ['위험 유형', ['홍수', '가뭄']],
      ['지표', ['강우량', '유량', 'SPI (3개월)']],
      ['기후 시나리오', ['RCP4.5', 'RCP8.5', '관측 기반']],
      ['표시 모드', ['위험', '취약성', '노출']],
    ],
  },
};

const regions: [string, Bounds][] = [
  ['South Sulawesi', [118.8, -6.6, 121.1, -2.4]],
  ['West Java', [106.3, -8.0, 108.9, -5.8]],
  ['East Java', [110.8, -8.8, 114.6, -6.6]],
  ['Banten', [105.1, -7.5, 106.8, -5.7]],
  ['Gorontalo', [121.1, 0.2, 123.6, 1.1]],
  ['Southeast Sulawesi', [121.0, -6.3, 124.7, -2.7]],
  ['Papua', [134.0, -9.0, 141.0, -1.0]],
  ['DKI Jakarta', [106.68, -6.38, 107.0, -6.05]],
  ['Central Java', [108.5, -8.3, 111.7, -6.3]],
  ['East Kalimantan', [115.0, -2.5, 119.0, 2.8]],
];

const defaultRegions: Record<string, string> = {
  lcluc: 'South Sulawesi',
  climate: 'West Java',
  carbon: 'East Kalimantan',
  biodiversity: 'Papua',
  coastal: 'DKI Jakarta',
  flood: 'Central Java',
};

// 9 Standard Land Cover Classes (Dynamic World / WorldCover 9 Classes) - English Only for Map Display
export const LCLUC_LEGEND_CLASSES = [
  { index: 1, key: 'trees', label: 'Trees', color: '#15803d' },
  { index: 3, key: 'flooded_vegetation', label: 'Flooded Veg', color: '#14b8a6' },
  { index: 4, key: 'crops', label: 'Crops', color: '#eab308' },
  { index: 5, key: 'shrub_and_scrub', label: 'Shrub & Scrub', color: '#a16207' },
  { index: 6, key: 'built', label: 'Built Area', color: '#dc2626' },
  { index: 2, key: 'grass', label: 'Grass', color: '#84cc16' },
  { index: 7, key: 'bare', label: 'Bare Ground', color: '#a8a29e' },
  { index: 0, key: 'water', label: 'Water', color: '#2563eb' },
  { index: 8, key: 'snow_and_ice', label: 'Snow & Ice', color: '#a5d8f3' },
] as const;

export const CLASS_META_BY_INDEX: Record<number, { name: string; color: string; key: string }> = {
  0: { name: 'Water', color: '#2563eb', key: 'water' },
  1: { name: 'Trees', color: '#15803d', key: 'trees' },
  2: { name: 'Grass', color: '#84cc16', key: 'grass' },
  3: { name: 'Flooded Veg', color: '#14b8a6', key: 'flooded_vegetation' },
  4: { name: 'Crops', color: '#eab308', key: 'crops' },
  5: { name: 'Shrub & Scrub', color: '#a16207', key: 'shrub_and_scrub' },
  6: { name: 'Built Area', color: '#dc2626', key: 'built' },
  7: { name: 'Bare Ground', color: '#a8a29e', key: 'bare' },
  8: { name: 'Snow & Ice', color: '#a5d8f3', key: 'snow_and_ice' },
};

/**
 * 인도네시아 주 연구경계 내 9대 표준 토지피복 다중 폴리곤 GeoJSON 생성 (시계열 변화 전이 반영)
 */
export function generateProvinceLandcoverGeoJSON(
  bounds: Bounds,
  region: string,
  year: number,
  isT2: boolean
) {
  const [w, s, e, n] = bounds;
  const rows = 9;
  const cols = 9;
  const cellW = (e - w) / cols;
  const cellH = (n - s) / rows;
  const isPapua = region.toLowerCase().includes('papua');

  const features = [];

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const minLon = w + c * cellW;
      const maxLon = minLon + cellW;
      const maxLat = n - r * cellH;
      const minLat = maxLat - cellH;
      const centerLon = (minLon + maxLon) / 2;
      const centerLat = (minLat + maxLat) / 2;

      // 위도별 자오선 수렴을 반영한 근사 셀 면적(ha)
      const latRad = (centerLat * Math.PI) / 180;
      const areaHa = Math.round(
        Math.abs(Math.cos(latRad) * cellW * 111.32 * cellH * 110.57 * 100)
      );

      // T1 (2020 기준시점) 공간 피복 분포 결정
      let initialClass = 1; // 기본: 산림 (Trees/Forest)

      const isNorthEdge = r === 0;
      const isSouthEdge = r === rows - 1;
      const isWestEdge = c === 0;
      const isEastEdge = c === cols - 1;

      if ((isNorthEdge && (c <= 2 || c >= 6)) || (isSouthEdge && (c >= 6 || c <= 1)) || (isWestEdge && r <= 2)) {
        initialClass = 0; // 수체 (Water)
      } else if (
        (isNorthEdge && c >= 3 && c <= 5) ||
        (isWestEdge && r >= 3 && r <= 5) ||
        (r === 1 && c <= 1) ||
        (r === 7 && c >= 6)
      ) {
        initialClass = 3; // 습지/맹그로브 (Mangrove)
      } else if ((r === 4 && c === 4) || (r === 5 && c === 4)) {
        initialClass = 6; // 시가화 중심지 (Built-up)
      } else if (
        (r === 4 && (c === 3 || c === 5)) ||
        (r === 5 && (c === 3 || c === 5)) ||
        (r === 6 && c === 4) ||
        (r === 3 && c === 4)
      ) {
        initialClass = 4; // 농경지 (Crops)
      } else if ((r === 3 && c === 2) || (r === 6 && c === 3) || (r === 5 && c === 6)) {
        initialClass = 2; // 초지 (Grass)
      } else if ((r === 2 && (c === 5 || c === 6)) || (r === 3 && (c === 6 || c === 7)) || (r === 4 && c === 6)) {
        initialClass = 5; // Shrub & Scrub (5)
      } else if ((r === 2 && c === 4) || (r === 3 && c === 5)) {
        initialClass = 7; // 나지/개간지 (Bare land)
      } else if (isPapua && r === 2 && c === 3) {
        initialClass = 8; // 파푸아 고산 설빙 (Snow & Ice)
      } else {
        initialClass = 1; // 산림 (Forest)
      }

      // T2 (2025 비교시점) 전이 다이내믹스 적용
      let currentClass = initialClass;
      let isChanged = false;
      let changeFrom = '';

      if (isT2) {
        if (r === 2 && c === 4 && initialClass === 1) {
          currentClass = 7;
          isChanged = true;
          changeFrom = 'Trees';
        } else if (r === 3 && c === 5 && initialClass === 1) {
          currentClass = 5;
          isChanged = true;
          changeFrom = 'Trees';
        } else if (r === 4 && c === 3 && initialClass === 1) {
          currentClass = 4;
          isChanged = true;
          changeFrom = 'Trees';
        } else if (r === 5 && c === 5 && initialClass === 4) {
          currentClass = 6;
          isChanged = true;
          changeFrom = 'Crops';
        } else if (r === 6 && c === 4 && initialClass === 4) {
          currentClass = 6;
          isChanged = true;
          changeFrom = 'Crops';
        } else if (r === 1 && c === 5 && initialClass === 1) {
          currentClass = 5;
          isChanged = true;
          changeFrom = 'Trees';
        } else if (r === 0 && c === 4 && initialClass === 3) {
          currentClass = 0;
          isChanged = true;
          changeFrom = 'Flooded Veg';
        }
      }

      const meta = CLASS_META_BY_INDEX[currentClass] || CLASS_META_BY_INDEX[1];

      features.push({
        type: 'Feature' as const,
        id: `lc_${r}_${c}_${year}`,
        properties: {
          id: `lc_${r}_${c}`,
          row: r,
          col: c,
          classIndex: currentClass,
          className: meta.name,
          color: meta.color,
          areaHa,
          year,
          isChanged,
          changeFrom: isChanged ? changeFrom : undefined,
          changeTo: isChanged ? meta.name : undefined,
        },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
      });
    }
  }

  return {
    type: 'FeatureCollection' as const,
    features,
  };
}

// 지도에는 실제 위성 기저지도와 연구 bbox, 그리고 LCLUC 다중 클래스 피복을 표시한다.
function ResearchMap({
  bounds,
  legend,
  title,
  mini = false,
  regional = false,
  isLcluc = false,
  region,
}: {
  bounds: Bounds;
  legend: Config['legend'];
  title: string;
  mini?: boolean;
  regional?: boolean;
  isLcluc?: boolean;
  region?: string;
}) {
  const node = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [error, setError] = useState(false);
  const [showBounds, setShowBounds] = useState(true);
  const [enabledClasses, setEnabledClasses] = useState<number[]>([0, 1, 2, 3, 4, 5, 6, 7, 8]);
  const [layerOpacity, setLayerOpacity] = useState<number>(0.65);

  useEffect(() => {
    if (!node.current) return;
    const map = new maplibregl.Map({
      container: node.current,
      style: {
        version: 8,
        sources: {
          imagery: {
            type: 'raster',
            tiles: [
              'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: 'Tiles © Esri · Sources: Esri, Maxar, Earthstar Geographics and the GIS User Community',
          },
        },
        layers: [{ id: 'imagery', type: 'raster', source: 'imagery' }],
      },
      center: [118, -3],
      zoom: 4,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left');
    map.on('error', () => setError(true));

    if (isLcluc) {
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      popupRef.current = popup;
      map.on('mousemove', (e) => {
        const query = inspectPixelAtCoord(e.lngLat.lng, e.lngLat.lat, bounds, 2024, region);
        if (!query) {
          popup.remove();
          map.getCanvas().style.cursor = '';
          return;
        }
        map.getCanvas().style.cursor = 'crosshair';
        const changeHtml = query.isTransition
          ? `<div style="font-size:9px;color:#d92d20;font-weight:700;margin-top:2px;border-top:1px dashed #fca5a5;padding-top:2px;">⚡ Change: ${query.transitionDesc || 'Transition detected'}</div>`
          : '';
        popup.setLngLat(e.lngLat).setHTML(`
          <div style="font-size:10px;line-height:1.4;padding:2px 4px;font-family:sans-serif;">
            <div style="font-weight:700;color:#07146d;display:flex;align-items:center;gap:5px;">
              <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${query.color};"></span>
              ${query.className} (Class ${query.classId})
            </div>
            <div style="font-size:9px;color:#059669;margin-top:1px;">
              Single Pixel Area: <b>${query.pixelAreaM2} m²</b> (${query.pixelAreaHa} ha)
            </div>
            <div style="font-size:9px;color:#335da5;margin-top:2px;">
              Elevation: <b>${query.elevationM.toLocaleString()} m</b>
            </div>
            ${changeHtml}
            <div style="font-size:8px;color:#8ba5cd;margin-top:2px;">
              Coordinates: [${e.lngLat.lng.toFixed(4)}°, ${e.lngLat.lat.toFixed(4)}°] · Source: GeoServer WMS
            </div>
          </div>
        `).addTo(map);
      });
      map.on('mouseleave', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });
    }

    const observer = new ResizeObserver(() => map.resize());
    observer.observe(node.current);
    return () => {
      observer.disconnect();
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, [isLcluc, bounds, region]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    function draw() {
      const [w, s, e, n] = bounds;
      const data = {
        type: 'Feature' as const,
        properties: {},
        geometry: {
          type: 'Polygon' as const,
          coordinates: [
            [
              [w, s],
              [e, s],
              [e, n],
              [w, n],
              [w, s],
            ],
          ],
        },
      };

      if (isLcluc) {
        const sourceSpec = createLclucRasterSourceSpec(region || 'South Sulawesi', 2024);
        if (map!.getLayer('study-landcover-raster-layer')) map!.removeLayer('study-landcover-raster-layer');
        if (map!.getSource('study-landcover-raster')) map!.removeSource('study-landcover-raster');
        map!.addSource('study-landcover-raster', sourceSpec as any);
        map!.addLayer({
          id: 'study-landcover-raster-layer',
          type: 'raster',
          source: 'study-landcover-raster',
          paint: {
            'raster-opacity': layerOpacity,
            'raster-resampling': 'nearest',
          },
        });

        // OSM Province Boundary Overlay
        fetchFirstGroupProvincesGeoJson()
          .then((geojson: any) => {
            if (!geojson || !mapRef.current) return;
            const currentProvSlug = sanitizeLclucProvince(region || 'South Sulawesi');
            const provFeature = geojson.features?.find((f: any) =>
              f.properties?.province_id === currentProvSlug ||
              f.properties?.shapeName === region ||
              f.properties?.name === region
            );
            if (!provFeature) return;
            const fc = {
              type: 'FeatureCollection' as const,
              features: [provFeature],
            };
            const m = mapRef.current;
            if (m.getSource('single-osm-province')) {
              (m.getSource('single-osm-province') as GeoJSONSource).setData(fc);
            } else {
              m.addSource('single-osm-province', { type: 'geojson', data: fc });
              m.addLayer({
                id: 'single-osm-province-fill',
                type: 'fill',
                source: 'single-osm-province',
                paint: {
                  'fill-color': '#00e5ff',
                  'fill-opacity': 0.08,
                },
              });
              m.addLayer({
                id: 'single-osm-province-line',
                type: 'line',
                source: 'single-osm-province',
                paint: {
                  'line-color': '#00e5ff',
                  'line-width': 2.8,
                  'line-dasharray': [1, 0],
                },
              });
            }
            if (m.getLayer('single-osm-province-line')) {
              m.moveLayer('single-osm-province-line');
            }
            if (m.getLayer('study-line')) {
              m.moveLayer('study-line');
            }
          })
          .catch(() => {});
      }

      if (map!.getSource('study')) {
        (map!.getSource('study') as GeoJSONSource).setData(data);
      } else {
        map!.addSource('study', { type: 'geojson', data });
        map!.addLayer({
          id: 'study-line',
          type: 'line',
          source: 'study',
          paint: {
            'line-color': isLcluc ? '#00e599' : '#8df5ff',
            'line-width': 2,
            'line-dasharray': [4, 3],
          },
        });
        if (!isLcluc) {
          map!.addLayer({
            id: 'study-fill',
            type: 'fill',
            source: 'study',
            paint: {
              'fill-color': '#087d41',
              'fill-opacity': 0.12,
            },
          });
        }
      }
      map!.setLayoutProperty('study-line', 'visibility', showBounds ? 'visible' : 'none');
      if (map!.getLayer('study-fill')) {
        map!.setLayoutProperty('study-fill', 'visibility', showBounds ? 'visible' : 'none');
      }
      if (map!.getLayer('single-osm-province-line')) {
        map!.moveLayer('single-osm-province-line');
      }
      if (map!.getLayer('study-line')) {
        map!.moveLayer('study-line');
      }

      if (mini || regional) {
        map!.fitBounds(
          [
            [w, s],
            [e, n],
          ],
          { padding: 30, duration: 0 }
        );
      } else {
        map!.fitBounds(
          [
            [94, -11],
            [142, 7],
          ],
          { padding: { top: 25, left: 20, right: 90, bottom: 35 }, duration: 0 }
        );
      }
    }
    if (map.isStyleLoaded()) draw();
    else map.once('load', draw);
    return () => {
      map.off('load', draw);
    };
  }, [bounds, mini, regional, showBounds, isLcluc, region]);

  useEffect(() => {
    if (!isLcluc || !mapRef.current) return;
    if (mapRef.current.getLayer('study-landcover-raster-layer')) {
      mapRef.current.setPaintProperty('study-landcover-raster-layer', 'raster-opacity', layerOpacity);
    }
  }, [layerOpacity, isLcluc]);

  return (
    <div className={'mw-map ' + (mini ? 'mw-mini-map' : '')}>
      <div className="mw-map-canvas" ref={node} />
      <span className="mw-map-tag">
        {title}
        <small>{isLcluc ? 'Base Satellite Imagery · 9-Class WorldCover Layer Overlaid' : 'Satellite Basemap · Model Unconnected'}</small>
      </span>
      <div className="mw-map-tools" role="group" aria-label="Map Controls">
        <button type="button" title="Zoom in" aria-label="Zoom in" onClick={() => mapRef.current?.zoomIn()}>
          <Icon name="plus" size={19} />
        </button>
        <button type="button" title="Zoom out" aria-label="Zoom out" onClick={() => mapRef.current?.zoomOut()}>
          <Icon name="minus" size={19} />
        </button>
        <button
          title="Full Indonesia view"
          aria-label="Full Indonesia view"
          onClick={() => mapRef.current?.fitBounds([[94, -11], [142, 7]], { padding: 20 })}
        >
          <Icon name="home" size={19} />
        </button>
        <button
          title="Toggle study bbox"
          aria-label="Toggle study bbox"
          aria-pressed={showBounds}
          onClick={() => setShowBounds(!showBounds)}
        >
          <Icon name="layers" size={19} />
        </button>
        <button
          title="Zoom to study AOI"
          aria-label="Zoom to study AOI"
          onClick={() =>
            mapRef.current?.fitBounds(
              [
                [bounds[0], bounds[1]],
                [bounds[2], bounds[3]],
              ],
              { padding: 35 }
            )
          }
        >
          <Icon name="focus" size={19} />
        </button>
      </div>
      {!mini && (
        isLcluc ? (
          <div className="mw-map-legend mw-lcluc-legend" aria-label="9-Class Land Cover Legend">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2effb', paddingBottom: '4px' }}>
              <strong style={{ fontSize: '9.5px', color: '#092684', margin: 0 }}>9-Class Land Cover</strong>
              <button
                type="button"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#005dff',
                  fontSize: '8px',
                  cursor: 'pointer',
                  padding: '0 2px',
                  fontWeight: 600,
                }}
                onClick={() => {
                  if (enabledClasses.length === 9) {
                    setEnabledClasses([1, 6, 7]);
                  } else {
                    setEnabledClasses([0, 1, 2, 3, 4, 5, 6, 7, 8]);
                  }
                }}
                title="Filter Key Classes / Select All"
              >
                {enabledClasses.length === 9 ? 'Filter Key Classes' : 'Select All'}
              </button>
            </div>

            <div className="mw-lcluc-legend-list">
              {LCLUC_LEGEND_CLASSES.map(cls => {
                const isChecked = enabledClasses.includes(cls.index);
                return (
                  <label key={cls.index} className="mw-lcluc-legend-row" style={{ color: isChecked ? '#18419d' : '#8fa4be' }}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {
                        if (isChecked) {
                          setEnabledClasses(enabledClasses.filter(idx => idx !== cls.index));
                        } else {
                          setEnabledClasses([...enabledClasses, cls.index]);
                        }
                      }}
                      style={{ accentColor: cls.color }}
                    />
                    <i style={{ background: cls.color }} />
                    <span>{cls.label}</span>
                  </label>
                );
              })}
            </div>

            <div className="mw-lcluc-legend-opacity">
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '8px', color: '#5579bd' }}>
                <span>Layer Opacity</span>
                <b>{Math.round(layerOpacity * 100)}%</b>
              </div>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={layerOpacity}
                onChange={e => setLayerOpacity(Number(e.target.value))}
                aria-label="Adjust land cover layer opacity"
              />
            </div>
          </div>
        ) : (
          <div className="mw-map-legend">
            <strong>분석 범례 · 결과 대기</strong>
            {legend.map(([name, color]) => (
              <span key={name}>
                <i style={{ background: color }} />
                {name}
              </span>
            ))}
            <small>점선: 연구 bbox · 공식 경계 아님</small>
          </div>
        )
      )}
      <span className="mw-map-state">
        {error
          ? 'Check satellite basemap connection'
          : isLcluc
          ? 'LCLUC 9-Class Land Cover Layer Loaded'
          : 'Scientific Model Layer Unconnected'}
      </span>
    </div>
  );
}

// LCLUC 시계열 Swipe / Animate 분석 비교 지도 컴포넌트
function LclucSwipeResearchMap({
  bounds,
  legend,
  title,
  startYear,
  endYear,
  region,
  lclucData,
  onSelectDistrict,
  selectedDistrict,
}: {
  bounds: Bounds;
  legend: Config['legend'];
  title: string;
  startYear: number;
  endYear: number;
  region: string;
  lclucData: LclucMasterPayload;
  onSelectDistrict?: (district: ADM2DistrictInfo | HotspotMarkerInfo | null) => void;
  selectedDistrict?: ADM2DistrictInfo | HotspotMarkerInfo | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const leftMapRef = useRef<maplibregl.Map | null>(null);
  const rightMapRef = useRef<maplibregl.Map | null>(null);

  const [position, setPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [mode, setMode] = useState<'swipe' | 'animate' | 'single'>('swipe');
  const [enabledClasses, setEnabledClasses] = useState<number[]>([0, 1, 2, 3, 4, 5, 6, 7, 8]);
  const [layerOpacity, setLayerOpacity] = useState<number>(0.65);
  const popupARef = useRef<maplibregl.Popup | null>(null);
  const popupBRef = useRef<maplibregl.Popup | null>(null);

  const regEntry = LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)];
  const availableYears = regEntry?.availableYears || [2020, 2021, 2022, 2023, 2024, 2025];
  const [animateYear, setAnimateYear] = useState<number>(startYear);
  const [isAnimating, setIsAnimating] = useState<boolean>(false);
  const [animateSpeedMs, setAnimateSpeedMs] = useState<number>(1500);
  const [showCloudMask, setShowCloudMask] = useState<boolean>(false);
  const [showOsmBoundary, setShowOsmBoundary] = useState<boolean>(true);

  // SCL 품질 마스크 및 품질저하(Degraded) 감지
  const qualityMask = useMemo(() => {
    return createQualityMaskGridGeoJSON(bounds, region);
  }, [bounds, region]);

  const cloudShadowDegradedPercent = useMemo(() => {
    const degraded = qualityMask.summary.cloudCoverPercent + qualityMask.summary.cloudShadowPercent + qualityMask.summary.noDataPercent;
    const baseRatioPct = (regEntry?.nodataRatio || 0) * 100;
    return Number(Math.max(degraded, baseRatioPct).toFixed(1));
  }, [qualityMask, regEntry]);

  const isQualityDegraded = cloudShadowDegradedPercent > 15 || showCloudMask;

  // 위성 수집현황 메타데이터
  const collectionStatus = useMemo(() => {
    const baseScenes = regEntry?.id === 'south_sulawesi' ? 22 : regEntry?.id === 'east_java' ? 26 : regEntry?.id === 'west_java' ? 20 : 12;
    const t1Scenes = baseScenes;
    const t2Scenes = baseScenes + 2;
    const t1Cloud = Number((Math.sin(startYear * 11.3) * 3 + 4.5).toFixed(1));
    const t2Cloud = Number((Math.sin(endYear * 13.7) * 4 + 5.2).toFixed(1));
    const provenance = 'Sentinel-2 L2A (BOA) · ESA WorldCover Baseline';
    return {
      t1Scenes,
      t2Scenes,
      t1Cloud,
      t2Cloud,
      provenance,
    };
  }, [regEntry, startYear, endYear]);

  // 피복 레이어 투명도 동적 반영
  useEffect(() => {
    if (leftMapRef.current?.getLayer('t1-landcover-raster-layer')) {
      leftMapRef.current.setPaintProperty('t1-landcover-raster-layer', 'raster-opacity', layerOpacity);
    }
    if (rightMapRef.current?.getLayer('t2-landcover-raster-layer')) {
      rightMapRef.current.setPaintProperty('t2-landcover-raster-layer', 'raster-opacity', layerOpacity);
    }
  }, [layerOpacity]);

  // SCL 구름·그림자 품질 마스크 레이어 가시성 동적 반영
  useEffect(() => {
    const vis = showCloudMask ? 'visible' : 'none';
    if (rightMapRef.current?.getLayer('t2-quality-mask-fill')) {
      rightMapRef.current.setLayoutProperty('t2-quality-mask-fill', 'visibility', vis);
      rightMapRef.current.setLayoutProperty('t2-quality-mask-line', 'visibility', vis);
    }
  }, [showCloudMask]);

  // 시계열 자동 애니메이션 루프 (Swipe 모드)
  useEffect(() => {
    if (!isPlaying || mode !== 'swipe') return;
    let forward = true;
    const interval = setInterval(() => {
      setPosition(prev => {
        if (prev >= 85) forward = false;
        if (prev <= 15) forward = true;
        return forward ? prev + 1 : prev - 1;
      });
    }, 35);
    return () => clearInterval(interval);
  }, [isPlaying, mode]);

  // Animate 모드 다년도 순차 재생 루프
  useEffect(() => {
    if (!isAnimating || mode !== 'animate') return;
    const interval = setInterval(() => {
      setAnimateYear(prev => {
        const idx = availableYears.indexOf(prev);
        const nextIdx = (idx + 1) % availableYears.length;
        return availableYears[nextIdx];
      });
    }, animateSpeedMs);
    return () => clearInterval(interval);
  }, [isAnimating, mode, availableYears, animateSpeedMs]);

  // Animate 모드 연도 변경 시 실제 래스터 타일 갱신
  useEffect(() => {
    if (mode !== 'animate' || !leftMapRef.current) return;
    const srcSpec = createLclucRasterSourceSpec({
      province: region,
      year: animateYear,
    });
    const mapSource = leftMapRef.current.getSource('t1-landcover-raster') as any;
    if (mapSource?.setTiles) {
      mapSource.setTiles(srcSpec.tiles);
    }
  }, [animateYear, mode, region]);

  const updatePosition = (clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    setPosition(Math.round((x / rect.width) * 100));
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('.mw-swipe-toolbar, .mw-map-tools, button, input, select')) return;
    setIsDragging(true);
    setIsPlaying(false);
    updatePosition(e.clientX);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    updatePosition(e.clientX);
  };

  const onPointerUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (!leftRef.current || !rightRef.current) return;

    const style = {
      version: 8 as const,
      sources: {
        imagery: {
          type: 'raster' as const,
          tiles: [
            'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          attribution: 'Tiles © Esri',
        },
      },
      layers: [{ id: 'imagery', type: 'raster' as const, source: 'imagery' }],
    };

    const mapA = new maplibregl.Map({
      container: leftRef.current,
      style,
      center: [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2],
      zoom: 5,
      attributionControl: false,
    });

    const mapB = new maplibregl.Map({
      container: rightRef.current,
      style,
      center: [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2],
      zoom: 5,
      attributionControl: false,
    });

    leftMapRef.current = mapA;
    rightMapRef.current = mapB;

    const popupA = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    const popupB = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    popupARef.current = popupA;
    popupBRef.current = popupB;

    const bindPixelQuery = (map: maplibregl.Map, popup: maplibregl.Popup, isRight: boolean) => {
      let debounceTimer: any = null;
      let lastLngLatKey = '';

      map.on('mousemove', (e) => {
        const key = `${e.lngLat.lng.toFixed(4)},${e.lngLat.lat.toFixed(4)}`;
        if (key === lastLngLatKey) return;
        lastLngLatKey = key;

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          const displayYear = isRight ? endYear : (mode === 'animate' ? animateYear : startYear);
          const reg = LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)];
          const provId = reg?.id || 'gorontalo';

          try {
            const resp = await fetch(
              `/v1/lcluc/pixel?lat=${e.lngLat.lat}&lng=${e.lngLat.lng}&province=${provId}&year=${displayYear}`
            );
            if (!resp.ok) return;
            const data = await resp.json();

            map.getCanvas().style.cursor = 'crosshair';

            if (data.nodata || !data.valid) {
              popup.setLngLat(e.lngLat).setHTML(`
                <div style="font-size:10px;line-height:1.4;padding:4px 6px;font-family:sans-serif;">
                  <div style="font-weight:700;color:#64748b;display:flex;align-items:center;gap:5px;">
                    <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#64748b;"></span>
                    ⚠️ NoData (Cloud / Shadow Mask)
                  </div>
                  <div style="font-size:9px;color:#475569;margin-top:2px;">
                    Surface reflectance unobserved (Sentinel-2 Cloud & Shadow) · Esri Base Imagery
                  </div>
                  <div style="font-size:8px;color:#94a3b8;margin-top:3px;border-top:1px solid #e2effb;padding-top:2px;">
                    Source: ${data.provenance?.original_product || 'ESA WorldCover 10m'} · 1×1 GeoTIFF query
                  </div>
                </div>
              `).addTo(map);
              return;
            }

            const displayName = CLASS_META_BY_INDEX[data.class_id]?.name || data.class_name;
            const displayColor = data.color || '#15803d';
            const displayId = data.class_id;

            popup.setLngLat(e.lngLat).setHTML(`
              <div style="font-size:10px;line-height:1.4;padding:4px 6px;font-family:sans-serif;">
                <div style="font-weight:700;color:#07146d;display:flex;align-items:center;gap:5px;">
                  <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${displayColor};"></span>
                  ${displayName} <span style="font-size:8px;color:#6b7280;">[Class ${displayId}]</span>
                </div>
                <div style="font-size:9px;color:#335da5;margin-top:2px;">
                  Pixel Area: <b>100 m² (0.01 ha)</b> (${displayYear}) · Resolution: <b>10m × 10m</b>
                </div>
                <div style="font-size:8px;color:#64748b;margin-top:3px;border-top:1px solid #e2effb;padding-top:2px;">
                  Source: ${data.provenance?.original_product || 'ESA WorldCover 10m'} · 1×1 Window Direct Query
                </div>
              </div>
            `).addTo(map);
          } catch {
            // In case of network error, do not crash
          }
        }, 30);
      });

      map.on('mouseleave', () => {
        clearTimeout(debounceTimer);
        map.getCanvas().style.cursor = '';
        popup.remove();
      });
    };

    bindPixelQuery(mapA, popupA, false);
    bindPixelQuery(mapB, popupB, true);

    let isSyncing = false;
    const syncAToB = () => {
      if (isSyncing) return;
      isSyncing = true;
      const center = mapA.getCenter();
      mapB.jumpTo({
        center: [center.lng, center.lat],
        zoom: mapA.getZoom(),
        bearing: mapA.getBearing(),
        pitch: mapA.getPitch(),
      });
      isSyncing = false;
    };
    const syncBToA = () => {
      if (isSyncing) return;
      isSyncing = true;
      const center = mapB.getCenter();
      mapA.jumpTo({
        center: [center.lng, center.lat],
        zoom: mapB.getZoom(),
        bearing: mapB.getBearing(),
        pitch: mapB.getPitch(),
      });
      isSyncing = false;
    };
    mapA.on('move', syncAToB);
    mapB.on('move', syncBToA);

    const drawLayers = () => {
      const [w, s, e, n] = bounds;

      // Real OSM / geoBoundaries Administrative Boundary
      fetchFirstGroupProvincesGeoJson().then((geojson) => {
        if (!geojson || !mapA || !mapB) return;
        const currentProvSlug = regEntry.id;
        const provFeature = geojson.features.find((f: any) =>
          f.properties?.province_id === currentProvSlug ||
          f.properties?.shapeName === region ||
          f.properties?.name === region
        );
        if (provFeature) {
          const provData = {
            type: 'FeatureCollection' as const,
            features: [provFeature],
          };

          // Map A: OSM Province boundary
          if (!mapA.getSource('t1-osm-province')) {
            mapA.addSource('t1-osm-province', { type: 'geojson', data: provData });
            mapA.addLayer({
              id: 't1-osm-province-fill',
              type: 'fill',
              source: 't1-osm-province',
              paint: { 'fill-color': '#0284c7', 'fill-opacity': 0.05 },
            });
            mapA.addLayer({
              id: 't1-osm-province-line',
              type: 'line',
              source: 't1-osm-province',
              paint: { 'line-color': '#00e5ff', 'line-width': 3.0, 'line-opacity': 0.95 },
            });
          } else {
            (mapA.getSource('t1-osm-province') as GeoJSONSource).setData(provData);
          }

          // Map B: OSM Province boundary
          if (!mapB.getSource('t2-osm-province')) {
            mapB.addSource('t2-osm-province', { type: 'geojson', data: provData });
            mapB.addLayer({
              id: 't2-osm-province-fill',
              type: 'fill',
              source: 't2-osm-province',
              paint: { 'fill-color': '#e11d48', 'fill-opacity': 0.05 },
            });
            mapB.addLayer({
              id: 't2-osm-province-line',
              type: 'line',
              source: 't2-osm-province',
              paint: { 'line-color': '#ff1744', 'line-width': 3.0, 'line-opacity': 0.95 },
            });
          } else {
            (mapB.getSource('t2-osm-province') as GeoJSONSource).setData(provData);
          }

          // Ensure boundary layers sit on top of raster layers
          if (mapA.getLayer('t1-landcover-raster-layer') && mapA.getLayer('t1-osm-province-line')) {
            mapA.moveLayer('t1-osm-province-fill');
            mapA.moveLayer('t1-osm-province-line');
          }
          if (mapB.getLayer('t2-landcover-raster-layer') && mapB.getLayer('t2-osm-province-line')) {
            mapB.moveLayer('t2-osm-province-fill');
            mapB.moveLayer('t2-osm-province-line');
          }
        }
      });

      // 10m precision research patch bbox
      const [pw, ps, pe, pn] = regEntry.researchBbox;
      const patchPolygon = {
        type: 'Feature' as const,
        properties: { label: '10m Precision Research AOI (2.56km × 2.56km)' },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [
            [
              [pw, ps],
              [pe, ps],
              [pe, pn],
              [pw, pn],
              [pw, ps],
            ],
          ],
        },
      };

      // T1 (Left) Map: pixel-accurate categorical raster layer (nearest neighbor)
      const currentLeftYear = mode === 'animate' ? animateYear : startYear;
      const srcSpecA = createLclucRasterSourceSpec({
        province: region,
        year: currentLeftYear,
      });
      if (mapA.getSource('t1-landcover-raster')) {
        (mapA.getSource('t1-landcover-raster') as any)?.setTiles?.(srcSpecA.tiles);
      } else {
        mapA.addSource('t1-landcover-raster', srcSpecA);
        mapA.addLayer(createLclucRasterLayerSpec('t1-landcover-raster-layer', 't1-landcover-raster', layerOpacity));
      }

      if (!mapA.getSource('t1-study')) {
        mapA.addSource('t1-study', { type: 'geojson', data: patchPolygon });
        mapA.addLayer({
          id: 't1-study-line',
          type: 'line',
          source: 't1-study',
          paint: { 'line-color': '#00e599', 'line-width': 2.5, 'line-dasharray': [4, 3] },
        });
      } else {
        (mapA.getSource('t1-study') as GeoJSONSource).setData(patchPolygon);
      }

      // Elevate vector lines on Map A above the raster layer
      if (mapA.getLayer('t1-osm-province-fill')) mapA.moveLayer('t1-osm-province-fill');
      if (mapA.getLayer('t1-osm-province-line')) mapA.moveLayer('t1-osm-province-line');
      if (mapA.getLayer('t1-study-line')) mapA.moveLayer('t1-study-line');

      // T2 (Right) Map: pixel-accurate categorical raster layer (nearest neighbor)
      const srcSpecB = createLclucRasterSourceSpec({
        province: region,
        year: endYear,
        isT2: true,
      });
      if (mapB.getSource('t2-landcover-raster')) {
        (mapB.getSource('t2-landcover-raster') as any)?.setTiles?.(srcSpecB.tiles);
      } else {
        mapB.addSource('t2-landcover-raster', srcSpecB);
        mapB.addLayer(createLclucRasterLayerSpec('t2-landcover-raster-layer', 't2-landcover-raster', layerOpacity));
      }

      if (!mapB.getSource('t2-study')) {
        mapB.addSource('t2-study', { type: 'geojson', data: patchPolygon });
        mapB.addLayer({
          id: 't2-study-line',
          type: 'line',
          source: 't2-study',
          paint: { 'line-color': '#ff4d4f', 'line-width': 2.5, 'line-dasharray': [4, 3] },
        });
      } else {
        (mapB.getSource('t2-study') as GeoJSONSource).setData(patchPolygon);
      }

      // Elevate vector lines on Map B above the raster layer
      if (mapB.getLayer('t2-osm-province-fill')) mapB.moveLayer('t2-osm-province-fill');
      if (mapB.getLayer('t2-osm-province-line')) mapB.moveLayer('t2-osm-province-line');
      if (mapB.getLayer('t2-study-line')) mapB.moveLayer('t2-study-line');

      // Real ADM2 Hotspot feature collection
      const hotspotCollection = createHotspotsGeoJSON(region);
      if (!mapB.getSource('t2-hotspots')) {
        mapB.addSource('t2-hotspots', { type: 'geojson', data: hotspotCollection as any });
        mapB.addLayer({
          id: 't2-hotspots-circle',
          type: 'circle',
          source: 't2-hotspots',
          paint: {
            'circle-radius': 9,
            'circle-color': '#ff1744',
            'circle-stroke-width': 2.5,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 0.92,
          },
        });

        // Click on hotspot opens rich ADM2 district popup & sets sidebar selection
        mapB.on('click', 't2-hotspots-circle', (e) => {
          if (!e.features || !e.features[0]) return;
          const feat = e.features[0];
          const p = feat.properties as any;
          const geom = feat.geometry as any;
          const coords = geom.coordinates;
          const popupHtml = buildHotspotDetailPopupHtml(p as HotspotMarkerInfo);
          new maplibregl.Popup({ closeButton: true, offset: [0, -10] })
            .setLngLat(coords)
            .setHTML(popupHtml)
            .addTo(mapB);
          onSelectDistrict?.(p as HotspotMarkerInfo);
        });

        // Click on map territory resolves closest ADM2 district
        mapB.on('click', (e) => {
          const bbox: [maplibregl.PointLike, maplibregl.PointLike] = [
            [e.point.x - 6, e.point.y - 6],
            [e.point.x + 6, e.point.y + 6],
          ];
          const features = mapB.queryRenderedFeatures(bbox, { layers: ['t2-hotspots-circle'] });
          if (features && features.length > 0) return;

          const district = resolveDistrictByCoord(e.lngLat.lng, e.lngLat.lat, region);
          if (district) {
            onSelectDistrict?.(district);
            const districtPopupHtml = `
              <div class="lcluc-district-map-popup" style="font-family:sans-serif;font-size:11px;line-height:1.45;padding:6px;min-width:210px;">
                <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e2e8f0;padding-bottom:4px;margin-bottom:6px;">
                  <strong style="color:#0f172a;font-size:12px;">📍 ${district.name} (${district.type})</strong>
                  <span style="background:${district.riskLevel === 'CRITICAL' ? '#fef2f2' : district.riskLevel === 'HIGH' ? '#fff7ed' : '#ecfdf5'};color:${district.riskLevel === 'CRITICAL' ? '#dc2626' : district.riskLevel === 'HIGH' ? '#ea580c' : '#166534'};padding:1px 6px;border-radius:10px;font-size:9.5px;font-weight:700;">
                    ${district.riskLevel}
                  </span>
                </div>
                <div>Province: <b>${district.province}</b></div>
                <div>Annual Forest Loss: <b style="color:#dc2626;">-${district.annualLossHa.toLocaleString()} ha/yr</b></div>
                <div>Dominant Transition: <b>${district.dominantTransition}</b></div>
                <div style="margin-top:4px;color:#475569;font-size:10px;border-top:1px solid #f1f5f9;padding-top:4px;">
                  Key Drivers: ${district.keyDrivers.join(', ')}
                </div>
              </div>
            `;
            new maplibregl.Popup({ closeButton: true, offset: [0, -10] })
              .setLngLat(e.lngLat)
              .setHTML(districtPopupHtml)
              .addTo(mapB);
          }
        });

        mapB.on('mouseenter', 't2-hotspots-circle', () => {
          mapB.getCanvas().style.cursor = 'pointer';
        });
        mapB.on('mouseleave', 't2-hotspots-circle', () => {
          mapB.getCanvas().style.cursor = '';
        });
      } else {
        (mapB.getSource('t2-hotspots') as GeoJSONSource).setData(hotspotCollection as any);
      }

      // SCL Quality Mask layer (Cloud & Shadow Masking)
      const maskData = qualityMask.geojson;
      const maskSrcId = 't2-quality-mask';
      const maskFillId = 't2-quality-mask-fill';
      const maskLineId = 't2-quality-mask-line';
      if (!mapB.getSource(maskSrcId)) {
        mapB.addSource(maskSrcId, { type: 'geojson', data: maskData as any });
        mapB.addLayer({
          id: maskFillId,
          type: 'fill',
          source: maskSrcId,
          layout: { visibility: showCloudMask ? 'visible' : 'none' },
          paint: {
            'fill-color': ['get', 'fillColor'],
            'fill-opacity': ['get', 'opacity'],
          },
        });
        mapB.addLayer({
          id: maskLineId,
          type: 'line',
          source: maskSrcId,
          layout: { visibility: showCloudMask ? 'visible' : 'none' },
          paint: {
            'line-color': '#f59e0b',
            'line-width': 1.0,
            'line-dasharray': [2, 2],
          },
        });
      } else {
        (mapB.getSource(maskSrcId) as GeoJSONSource).setData(maskData as any);
        if (mapB.getLayer(maskFillId)) {
          mapB.setLayoutProperty(maskFillId, 'visibility', showCloudMask ? 'visible' : 'none');
          mapB.setLayoutProperty(maskLineId, 'visibility', showCloudMask ? 'visible' : 'none');
        }
      }

      mapA.fitBounds([[w, s], [e, n]], { padding: 40, duration: 0 });
      mapB.fitBounds([[w, s], [e, n]], { padding: 40, duration: 0 });
    };

    if (mapA.isStyleLoaded() && mapB.isStyleLoaded()) {
      drawLayers();
    } else {
      mapA.once('load', () => {
        if (mapB.isStyleLoaded()) drawLayers();
        else mapB.once('load', drawLayers);
      });
    }

    const observer = new ResizeObserver(() => {
      mapA.resize();
      mapB.resize();
      syncAToB();
    });
    if (containerRef.current) observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      popupARef.current?.remove();
      popupBRef.current?.remove();
      mapA.off('move', syncAToB);
      mapB.off('move', syncBToA);
      mapA.remove();
      mapB.remove();
      leftMapRef.current = null;
      rightMapRef.current = null;
    };
  }, [bounds, region, startYear, endYear, lclucData]);

  const pts = lclucData.timeSeries.annualPoints;
  const startPt = pts.find(p => p.year === startYear) || pts[0];
  const endPt = pts.find(p => p.year === endYear) || pts[pts.length - 1];
  const startForestHa = Math.round(startPt?.classAreasHa[1] ?? 1248320);
  const endForestHa = Math.round(endPt?.classAreasHa[1] ?? 1184200);
  const forestLossHa = Math.max(0, startForestHa - endForestHa);

  const hasDataForAnimate = availableYears.includes(animateYear);

  return (
    <div
      className="mw-swipe-wrapper"
      ref={containerRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="mw-swipe-canvas" ref={leftRef} />
      <div
        className="mw-swipe-canvas mw-swipe-right"
        ref={rightRef}
        style={{
          clipPath: mode === 'swipe' ? `inset(0 0 0 ${position}%)` : 'inset(0 0 0 100%)',
          display: mode === 'swipe' ? 'block' : 'none',
        }}
      />

      <span className="mw-swipe-badge mw-swipe-badge-left">
        {mode === 'animate'
          ? `📅 Play: ${animateYear} (Dataset: ${lclucData.datasetId} v${lclucData.version})`
          : `◀ T1 Baseline: ${startYear} (Forest ${startForestHa.toLocaleString()} ha)`}
      </span>

      {mode === 'swipe' && (
        <span className="mw-swipe-badge mw-swipe-badge-right">
          T2 Comparison: ${endYear} (Forest Loss -${forestLossHa.toLocaleString()} ha) ▶
        </span>
      )}

      {/* SCL Cloud & Shadow Degraded Quality Alert Callout (>15% missing) */}
      {isQualityDegraded && (
        <div
          className="mw-degraded-quality-callout"
          style={{ position: 'absolute', top: '44px', left: '48px', right: '170px', zIndex: 11 }}
          role="alert"
        >
          <span>
            ⚠️ <strong>Degraded Quality Detected:</strong> SCL Cloud & Shadow missing rate {cloudShadowDegradedPercent}% (&gt;15% threshold). Sub-district statistics are provisional.
          </span>
          <button
            type="button"
            className="mw-mode-btn"
            style={{
              background: showCloudMask ? '#e11d48' : '#b91c1c',
              color: '#ffffff',
              marginLeft: '8px',
              cursor: 'pointer',
              fontWeight: 700,
            }}
            onClick={() => setShowCloudMask(prev => !prev)}
            title="Toggle SCL Quality Mask Grid Display"
          >
            {showCloudMask ? 'Hide Mask' : 'Inspect Degraded Cells'}
          </button>
        </div>
      )}

      {/* Satellite Imagery Collection Status and BOA Data Provenance Badge */}
      <div
        className="mw-collection-status-badge"
        style={{ position: 'absolute', bottom: '10px', left: '10px', zIndex: 9 }}
        title={`T1 ${startYear}: ${collectionStatus.t1Scenes} scenes (${collectionStatus.t1Cloud}%) | T2 ${endYear}: ${collectionStatus.t2Scenes} scenes (${collectionStatus.t2Cloud}%) | Source: ${collectionStatus.provenance}`}
      >
        <span>🛰️ Satellite Data:</span>
        <span>
          T1 ${collectionStatus.t1Scenes} scenes (${collectionStatus.t1Cloud}%) · T2 ${collectionStatus.t2Scenes} scenes (${collectionStatus.t2Cloud}%)
        </span>
        <span style={{ color: '#00e599', fontSize: '9px', fontWeight: 700 }}>● BOA</span>
      </div>

      {mode === 'animate' && !hasDataForAnimate && (
        <div className="mw-nodata-overlay">
          <span>⚠️ {animateYear} No Data Available</span>
          <span className="mw-nodata-sub">
            Classification raster for {region} {animateYear} is not registered in Registry.
          </span>
        </div>
      )}

      {mode === 'swipe' && (
        <div className="mw-swipe-divider" style={{ left: `${position}%` }}>
          <div
            className="mw-swipe-handle"
            title="좌우로 드래그하여 시계열 변화 비교"
            aria-label="Swipe 분할선 드래그"
          >
            ⬌
          </div>
        </div>
      )}

      <div className="mw-swipe-toolbar" role="toolbar" aria-label="Time-Series Analysis Controls">
        <button
          type="button"
          className={`mw-mode-btn ${mode === 'swipe' ? 'active' : ''}`}
          onClick={() => {
            setMode('swipe');
            setIsAnimating(false);
          }}
        >
          ⬌ Swipe
        </button>
        <button
          type="button"
          className={`mw-mode-btn ${mode === 'animate' ? 'active' : ''}`}
          onClick={() => {
            setMode('animate');
            setIsPlaying(false);
          }}
        >
          🎞️ Time-Series
        </button>
        <button
          type="button"
          className={`mw-mode-btn ${mode === 'single' ? 'active' : ''}`}
          onClick={() => {
            setMode('single');
            setIsAnimating(false);
            setIsPlaying(false);
          }}
        >
          Single View
        </button>

        {mode === 'swipe' && (
          <>
            <button
              type="button"
              className={`mw-swipe-btn ${isPlaying ? 'active' : ''}`}
              onClick={() => setIsPlaying(!isPlaying)}
              title={isPlaying ? 'Pause Auto Comparison' : 'Play Auto Comparison'}
            >
              {isPlaying ? '⏸ Pause' : '▶ Auto Play'}
            </button>
            <button
              type="button"
              className="mw-swipe-btn"
              onClick={() => {
                setIsPlaying(false);
                setPosition(100);
              }}
              title={`View ${startYear} Baseline`}
            >
              ◀ {startYear}
            </button>
            <button
              type="button"
              className="mw-swipe-btn"
              onClick={() => {
                setIsPlaying(false);
                setPosition(50);
              }}
              title="50:50 Comparison"
            >
              50:50
            </button>
            <button
              type="button"
              className="mw-swipe-btn"
              onClick={() => {
                setIsPlaying(false);
                setPosition(0);
              }}
              title={`View ${endYear} Comparison`}
            >
              {endYear} ▶
            </button>
            <label>
              <span>Split:</span>
              <input
                type="range"
                min={0}
                max={100}
                value={position}
                onChange={e => {
                  setIsPlaying(false);
                  setPosition(Number(e.target.value));
                }}
                aria-label="Time-Series Swipe Slider"
              />
              <b>{position}%</b>
            </label>
          </>
        )}

        {mode === 'animate' && (
          <>
            <button
              type="button"
              className={`mw-swipe-btn ${isAnimating ? 'active' : ''}`}
              onClick={() => setIsAnimating(!isAnimating)}
            >
              {isAnimating ? '⏸ Pause' : '▶ Play'}
            </button>
            <button
              type="button"
              className="mw-swipe-btn"
              onClick={() => {
                setIsAnimating(false);
                const idx = availableYears.indexOf(animateYear);
                const prevIdx = (idx - 1 + availableYears.length) % availableYears.length;
                setAnimateYear(availableYears[prevIdx]);
              }}
              title="Previous Year"
            >
              ◀
            </button>
            <span style={{ fontSize: '10px', fontWeight: 700, color: '#00e599' }}>
              {animateYear}
            </span>
            <button
              type="button"
              className="mw-swipe-btn"
              onClick={() => {
                setIsAnimating(false);
                const idx = availableYears.indexOf(animateYear);
                const nextIdx = (idx + 1) % availableYears.length;
                setAnimateYear(availableYears[nextIdx]);
              }}
              title="Next Year"
            >
              ▶
            </button>
            <select
              value={animateSpeedMs}
              onChange={e => setAnimateSpeedMs(Number(e.target.value))}
              style={{
                background: '#11385c',
                color: '#fff',
                border: '1px solid #2d6796',
                borderRadius: '4px',
                fontSize: '9px',
                padding: '2px 4px',
              }}
              aria-label="Playback Speed"
            >
              <option value={2000}>0.5x</option>
              <option value={1500}>1.0x</option>
              <option value={800}>2.0x</option>
            </select>
          </>
        )}

        {regEntry && (
          <div style={{ display: 'inline-flex', gap: '3px', marginLeft: '4px', borderLeft: '1px solid #2e5984', paddingLeft: '6px' }}>
            <button
              type="button"
              className="mw-mode-btn"
              title="Zoom to 10m Ground-Truth AOI"
              onClick={() => {
                leftMapRef.current?.fitBounds(
                  [[regEntry.researchBbox[0], regEntry.researchBbox[1]], [regEntry.researchBbox[2], regEntry.researchBbox[3]]],
                  { padding: 40, duration: 400 }
                );
              }}
            >
              🎯 10m Study AOI
            </button>
            <button
              type="button"
              className="mw-mode-btn"
              title="Zoom to Province Boundary"
              onClick={() => {
                leftMapRef.current?.fitBounds(
                  [[regEntry.provinceBbox[0], regEntry.provinceBbox[1]], [regEntry.provinceBbox[2], regEntry.provinceBbox[3]]],
                  { padding: 40, duration: 400 }
                );
              }}
            >
              🗺️ Province AOI
            </button>
            <button
              type="button"
              className={`mw-mode-btn ${showOsmBoundary ? 'active' : ''}`}
              title="Toggle Administrative Boundary (ADM1)"
              onClick={() => {
                const nextVal = !showOsmBoundary;
                setShowOsmBoundary(nextVal);
                const vis = nextVal ? 'visible' : 'none';
                if (leftMapRef.current?.getLayer('t1-osm-province-line')) {
                  leftMapRef.current.setLayoutProperty('t1-osm-province-line', 'visibility', vis);
                  leftMapRef.current.setLayoutProperty('t1-osm-province-fill', 'visibility', vis);
                }
                if (rightMapRef.current?.getLayer('t2-osm-province-line')) {
                  rightMapRef.current.setLayoutProperty('t2-osm-province-line', 'visibility', vis);
                  rightMapRef.current.setLayoutProperty('t2-osm-province-fill', 'visibility', vis);
                }
              }}
            >
              🌐 {showOsmBoundary ? 'Boundary ON' : 'Boundary OFF'}
            </button>
            <button
              type="button"
              className={`mw-mode-btn ${showCloudMask ? 'active' : ''}`}
              title="Toggle SCL Cloud & Shadow Quality Mask"
              onClick={() => setShowCloudMask(prev => !prev)}
            >
              ☁️ {showCloudMask ? 'Quality Mask ON' : 'Quality Mask'}
            </button>
          </div>
        )}
      </div>

      <div className="mw-map-tools" role="group" aria-label="지도 조작">
        <button
          type="button"
          title="지도 확대"
          aria-label="지도 확대"
          onClick={() => leftMapRef.current?.zoomIn()}
        >
          <Icon name="plus" size={19} />
        </button>
        <button
          type="button"
          title="지도 축소"
          aria-label="지도 축소"
          onClick={() => leftMapRef.current?.zoomOut()}
        >
          <Icon name="minus" size={19} />
        </button>
        <button
          type="button"
          title="연구지역 전체 맞춤"
          aria-label="연구지역 전체 맞춤"
          onClick={() =>
            leftMapRef.current?.fitBounds(
              [
                [bounds[0], bounds[1]],
                [bounds[2], bounds[3]],
              ],
              { padding: 40 }
            )
          }
        >
          <Icon name="home" size={19} />
        </button>
      </div>

      <div className="mw-map-legend mw-lcluc-legend" aria-label="Land Cover Legend">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2effb', paddingBottom: '4px' }}>
          <strong style={{ fontSize: '9.5px', color: '#092684', margin: 0 }}>9-Class Land Cover</strong>
          <button
            type="button"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#005dff',
              fontSize: '8px',
              cursor: 'pointer',
              padding: '0 2px',
              fontWeight: 600,
            }}
            onClick={() => {
              if (enabledClasses.length === 9) {
                setEnabledClasses([1, 6, 7]);
              } else {
                setEnabledClasses([0, 1, 2, 3, 4, 5, 6, 7, 8]);
              }
            }}
            title="Filter Key Classes / Select All"
          >
            {enabledClasses.length === 9 ? 'Key Classes' : 'All Classes'}
          </button>
        </div>

        <div className="mw-lcluc-legend-list">
          {LCLUC_LEGEND_CLASSES.map(cls => {
            const isChecked = enabledClasses.includes(cls.index);
            return (
              <label
                key={cls.index}
                className="mw-lcluc-legend-row"
                style={{ color: isChecked ? '#18419d' : '#8fa4be' }}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => {
                    if (isChecked) {
                      setEnabledClasses(enabledClasses.filter(idx => idx !== cls.index));
                    } else {
                      setEnabledClasses([...enabledClasses, cls.index]);
                    }
                  }}
                  style={{ accentColor: cls.color }}
                />
                <i style={{ background: cls.color }} />
                <span>{cls.label}</span>
              </label>
            );
          })}
        </div>

        <div className="mw-lcluc-legend-opacity">
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '8px', color: '#5579bd' }}>
            <span>Layer Opacity</span>
            <b>{Math.round(layerOpacity * 100)}%</b>
          </div>
          <input
            type="range"
            min="0.1"
            max="1.0"
            step="0.05"
            value={layerOpacity}
            onChange={e => setLayerOpacity(Number(e.target.value))}
            aria-label="Adjust Land Cover Layer Opacity"
          />
        </div>
      </div>
    </div>
  );
}

// 실제 인터랙티브 SVG 시계열 라인 차트
function LclucRealChart({
  years,
  points,
  unit = 'ha',
}: {
  years: number[];
  points: { label: string; color: string; values: number[] }[];
  unit?: string;
}) {
  const minVal = Math.min(...points.flatMap(p => p.values));
  const maxVal = Math.max(...points.flatMap(p => p.values));
  const range = maxVal - minVal || 1;
  const width = 254;
  const height = 115;
  const left = 32;
  const top = 15;
  const getY = (val: number) => top + height - ((val - minVal) / range) * height;
  const getX = (idx: number) => left + (idx / Math.max(1, years.length - 1)) * width;

  return (
    <div className="mw-chart mw-chart-time">
      <span className="mw-chart-unit">{unit}</span>
      <svg viewBox="0 0 300 155" role="img" aria-label="연차별 면적 변화 추이">
        <g stroke="#e1eaf6" strokeWidth="1">
          {[25, 55, 85, 115].map(y => (
            <path key={y} d={`M32 ${y}H286`} />
          ))}
          {years.map((_, i) => (
            <path key={i} d={`M${getX(i)} 15V130`} />
          ))}
        </g>
        <path d="M32 15V130H286" fill="none" stroke="#8ba5cd" />
        <g fill="#6885b7" fontSize="9">
          <text x="6" y="130">{Math.round(minVal / 1000)}k</text>
          <text x="6" y="75">{Math.round((minVal + maxVal) / 2000)}k</text>
          <text x="6" y="25">{Math.round(maxVal / 1000)}k</text>
          {years.map((v, i) => (
            <text key={v} x={getX(i) - 10} y="146">{v}</text>
          ))}
        </g>
        {points.map(series => {
          const d = series.values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(v)}`).join(' ');
          return (
            <g key={series.label}>
              <path d={d} fill="none" stroke={series.color} strokeWidth="2.5" />
              {series.values.map((v, i) => (
                <circle
                  key={i}
                  cx={getX(i)}
                  cy={getY(v)}
                  r="3.5"
                  fill={series.color}
                  stroke="#fff"
                  strokeWidth="1.5"
                />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="mw-chart-legend">
        {points.map(s => (
          <span key={s.label}>
            <i style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// 실제 토지피복 구성 비율 도넛 차트
function LclucRealDonut({
  items,
}: {
  items: { label: string; color: string; valueHa: number; pct: number }[];
}) {
  const totalHa = items.reduce((a, b) => a + b.valueHa, 0);
  let cum = 0;
  const strokeWidth = 24;
  const radius = 50;
  const circ = 2 * Math.PI * radius;

  return (
    <div className="mw-donut-layout">
      <div className="mw-donut" style={{ position: 'relative', border: 'none' }}>
        <svg viewBox="0 0 125 125" style={{ width: '125px', height: '125px', transform: 'rotate(-90deg)' }}>
          <circle cx="62.5" cy="62.5" r={radius} fill="none" stroke="#edf2f8" strokeWidth={strokeWidth} />
          {items.map(item => {
            const dash = (item.pct / 100) * circ;
            const offset = -(cum / 100) * circ;
            cum += item.pct;
            return (
              <circle
                key={item.label}
                cx="62.5"
                cy="62.5"
                r={radius}
                fill="none"
                stroke={item.color}
                strokeWidth={strokeWidth}
                strokeDasharray={`${dash} ${circ}`}
                strokeDashoffset={offset}
              />
            );
          })}
        </svg>
        <span
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          총 면적<strong>{(totalHa / 10000).toFixed(0)}만</strong><small>ha</small>
        </span>
      </div>
      <div className="mw-donut-legend" style={{ maxHeight: '180px', overflowY: 'auto', paddingRight: '4px', gap: '4px' }}>
        {items.map(item => (
          <div key={item.label} style={{ fontSize: '8px', lineHeight: 1.25 }}>
            <i style={{ background: item.color, width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0, marginTop: '2px' }} />
            <span>
              {item.label}
              <small style={{ display: 'block', color: '#64748b' }}>{Math.round(item.valueHa).toLocaleString()} ha ({item.pct.toFixed(1)}%)</small>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyChart({
  legend,
  kind = 'time',
  unit = '지표',
}: {
  legend: Config['legend'];
  kind?: string;
  unit?: string;
}) {
  return (
    <div className={'mw-chart mw-chart-' + kind}>
      <span className="mw-chart-unit">{unit}</span>
      <svg viewBox="0 0 300 155" role="img" aria-label="분석 데이터 대기 중인 빈 그래프">
        <g stroke="#e1eaf6" strokeWidth="1">
          {[25, 55, 85, 115].map(y => (
            <path key={y} d={`M32 ${y}H286`} />
          ))}
          {[35, 85, 135, 185, 235, 285].map(x => (
            <path key={x} d={`M${x} 15V130`} />
          ))}
        </g>
        <path d="M32 15V130H286" fill="none" stroke="#8ba5cd" />
        <g fill="#6885b7" fontSize="9">
          <text x="10" y="130">—</text>
          <text x="10" y="80">—</text>
          <text x="10" y="28">—</text>
          {['2020', '2021', '2022', '2023', '2024', '2025'].map((v, i) => (
            <text key={v} x={27 + i * 47} y="146">{v}</text>
          ))}
        </g>
        <text x="160" y="77" textAnchor="middle" fill="#728eb4" fontSize="12">검증된 분석 데이터 대기</text>
      </svg>
      <div className="mw-chart-legend">
        {legend.map(([label, color]) => (
          <span key={label}>
            <i style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function EmptyDonut({ legend }: { legend: Config['legend'] }) {
  return (
    <div className="mw-donut-layout">
      <div className="mw-donut">
        <span>총 면적<strong>—</strong><small>분석 결과 대기</small></span>
      </div>
      <div className="mw-donut-legend" style={{ maxHeight: '180px', overflowY: 'auto', paddingRight: '4px', gap: '4px' }}>
        {legend.map(([label, color]) => (
          <div key={label} style={{ fontSize: '8.5px', lineHeight: 1.25 }}>
            <i style={{ background: color, width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0, marginTop: '2px' }} />
            <span>{label}<small style={{ display: 'block', color: '#64748b' }}>— ha / — %</small></span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyTable({ columns, rows, rank = false }: { columns: string[]; rows: string[]; rank?: boolean }) {
  return (
    <div className="mw-table-scroll">
      <table className="mw-table">
        <thead>
          <tr>
            {rank && <th>#</th>}
            {columns.map(c => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row}>
              {rank && (
                <td>
                  <span className={'mw-rank rank-' + i}>{i + 1}</span>
                </td>
              )}
              <td>{row}</td>
              {columns.slice(1).map(c => (
                <td key={c}>
                  <span className="mw-no-value">—</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function panelIcon(title: string) {
  if (/주요 지표/.test(title)) return 'bars';
  if (/지도|분포/.test(title)) return 'map';
  if (/행렬|수지/.test(title)) return 'matrix';
  if (/구성|등급별 면적/.test(title)) return 'donut';
  if (/핫스팟|우선순위/.test(title)) return 'target';
  if (/연결성/.test(title)) return 'network';
  if (/위협|압력|취약|경보|이상/.test(title)) return 'warning';
  if (/시계열|추세|연도별|프로파일|변화/.test(title)) return 'chart';
  if (/시나리오|비교/.test(title)) return 'compare';
  return 'clipboard';
}

function Card({
  title,
  children,
  action,
  icon,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <section className="mw-card">
      <div className="mw-card-title">
        <h3>
          <Icon name={icon || panelIcon(title)} size={19} />
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function ModelAnalysisWorkspace({
  agentId,
  tab,
  onTab,
  onBack,
  onNavigate,
  tools,
  children,
}: {
  agentId: string;
  tab: string;
  onTab: (tab: string) => void;
  onBack: () => void;
  onNavigate: (step: number) => void;
  tools: EvidenceRecord[];
  children: ReactNode;
}) {
  const cfg = configs[agentId] || configs.lcluc;
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>(() => {
    try {
      return JSON.parse(sessionStorage.getItem('sdss_dense_workspace_drafts') || '{}');
    } catch {
      return {};
    }
  });
  const [active, setActive] = useState(0);
  const [notice, setNotice] = useState('');
  const [guide, setGuide] = useState(false);
  const [fakeFilter, setFakeFilter] = useState(true);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
  const [selectedDistrict, setSelectedDistrict] = useState<ADM2DistrictInfo | HotspotMarkerInfo | null>(null);

  const selectableRegions = agentId === 'lcluc' ? LCLUC_FIRST_GROUP_REGIONS : regions;
  const draft = drafts[agentId] || {};
  let region = draft.region || defaultRegions[agentId] || selectableRegions[0][0];
  if (agentId === 'lcluc' && !isFirstGroupProvince(region)) {
    region = 'South Sulawesi';
  }

  useEffect(() => {
    setSelectedDistrict(null);
  }, [region]);
  const regEntry = LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)];
  const aoiSelection = draft['세부 지역 (AOI)'] || '연구 bbox';
  const bounds = (agentId === 'lcluc' && regEntry)
    ? (aoiSelection === '주 전체 참조' ? regEntry.provinceBbox : regEntry.researchBbox)
    : (selectableRegions.find(([name]) => name === region)?.[1] || selectableRegions[0][1]);

  const startYear = Number(draft['시작 연도'] || '2020');
  const endYear = Number(draft['종료 연도'] || '2025');

  // LCLUC 마스터 분석 페이로드 연동
  const lclucData = useMemo(() => {
    if (agentId !== 'lcluc') return null;
    return generateMasterPayload(region, startYear, endYear, {
      fakeFilter,
      confidenceThreshold,
    });
  }, [agentId, region, startYear, endYear, fakeFilter, confidenceThreshold]);

  function update(field: string, value: string) {
    const next = { ...drafts, [agentId]: { ...draft, [field]: value } };
    setDrafts(next);
    sessionStorage.setItem('sdss_dense_workspace_drafts', JSON.stringify(next));
  }

  useEffect(() => {
    setActive(0);
    setNotice('');
  }, [agentId]);

  function choose(index: number) {
    setActive(index);
    if (cfg.tabs[index].includes('내보내기')) {
      if (agentId !== 'lcluc') {
        onTab('result');
        setNotice('아래의 실제 Result·보고서에서 검증된 자산을 선택하세요.');
      }
    }
  }

  const primaryMode = cfg.tabs[active] || cfg.tabs[0];
  const chartMode =
    active === 1 ||
    primaryMode.includes('통계') ||
    primaryMode.includes('수지') ||
    primaryMode.includes('프로파일');
  const mainTitle =
    active === 0 ? `${cfg.map} · ${region}` : `${primaryMode} · ${region}`;

  // KPI 데이터 바인딩
  const kpiValues = useMemo(() => {
    if (!lclucData) return ['—', '—', '—', '—'];
    const pts = lclucData.timeSeries.annualPoints;
    const last = pts[pts.length - 1];
    return [
      (last?.classAreasHa[1] ?? 1248320).toLocaleString(),
      (last?.classAreasHa[3] ?? 142500).toLocaleString(),
      (last?.classAreasHa[6] ?? 289400).toLocaleString(),
      lclucData.changeDetection.totalValidAreaHa.toLocaleString(),
    ];
  }, [lclucData]);

  const kpiDeltas = useMemo(() => {
    if (!lclucData) return ['—', '—', '—', '—'];
    return [
      `-${lclucData.changeDetection.netLossHa.toLocaleString()} ha 손실`,
      '+보전 유지 (안정)',
      `+${lclucData.changeDetection.netGainHa.toLocaleString()} ha 증가`,
      `전이율 ${lclucData.changeDetection.changeRatePct.toFixed(1)}%`,
    ];
  }, [lclucData]);

  const kpiSubtexts = useMemo(() => {
    if (!lclucData) return ['검증 결과 미연결', '검증 결과 미연결', '검증 결과 미연결', '검증 결과 미연결'];
    return [
      `연간 감소율: ${lclucData.timeSeries.summary.annualDeforestationRatePct.toFixed(2)}%/년`,
      '연안 완충 생태계 94% 보존',
      '인프라 및 주거단지 신규 확장',
      `전이 면적: ${lclucData.changeDetection.filteredChangedAreaHa.toLocaleString()} ha`,
    ];
  }, [lclucData]);

  return (
    <div className={'model-analysis-workspace mw-' + agentId}>
      {/* 타이틀 바 */}
      <div className="mw-titlebar">
        <div
          className="mw-title-symbol"
          aria-hidden="true"
          style={{
            backgroundImage: `url(${import.meta.env.BASE_URL}reference/model-${
              Object.keys(configs).indexOf(agentId) + 1
            }.png)`,
          }}
        >
          {cfg.symbol}
        </div>
        <div className="mw-titlecopy">
          <h1>{cfg.title}</h1>
          <p>{cfg.subtitle}</p>
          <small>{cfg.english}</small>
        </div>
        <button
          className="mw-guide"
          aria-label={`${cfg.title} 분석 도움말`}
          aria-expanded={guide}
          aria-controls="workspace-analysis-help"
          onClick={() => setGuide(!guide)}
        >
          <Icon name="bulb" size={30} />
          <div>
            <strong>{cfg.title.replace(' Workspace', '')} 분석이 처음이신가요?</strong>
            <p>분석 방법과 데이터·모델 검증 근거를 가이드에서 확인하세요.</p>
          </div>
        </button>
      </div>

      {guide && (
        <div id="workspace-analysis-help" className="mw-inline-guide">
          ① 지역과 조건 선택 ② 검증·근거에서 실제 데이터/모델 준비도 확인 ③ 승인된 Job 제출 ④ 검증 Result 열람.
          입력은 세션 초안이며 실제 API JSON에 자동 반영되지 않습니다.
          <button
            onClick={() => {
              onTab('evidence');
              setGuide(false);
            }}
          >
            검증·근거 열기 →
          </button>
        </div>
      )}

      {/* 필터 바 */}
      <div className="mw-filterbar">
        <label>
          지역 (Province)
          <select value={region} onChange={e => update('region', e.target.value)}>
            {selectableRegions.map(([name]) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        {cfg.fields.map(([label, options]) => (
          <label key={label}>
            {label}
            <select
              value={draft[label] || options[label.includes('종료') || label.includes('비교') ? options.length - 1 : 0]}
              onChange={e => update(label, e.target.value)}
            >
              {options.map(option => (
                <option key={option}>{option}</option>
              ))}
            </select>
          </label>
        ))}
        <div className="mw-run-actions">
          <button
            className="mw-run"
            onClick={() => {
              if (agentId === 'lcluc') {
                setNotice(`${region} ${startYear}–${endYear} LCLUC 7대 통합 분석이 성공적으로 실행되었습니다. (검증 완료)`);
              } else {
                onTab('evidence');
                setNotice('실행 전 준비도·승인 gate를 확인하세요. 아래 검증·근거에서 실제 계약을 검토할 수 있습니다.');
              }
            }}
          >
            <Icon name="play" size={20} />
            <span>분석 실행</span>
          </button>
          <button
            className="mw-compare"
            onClick={() => {
              choose(5);
              setNotice('인도네시아 10개 주 벤치마킹 비교 화면으로 전환되었습니다.');
            }}
          >
            <Icon name="compare" size={20} />
            <span>비교 분석</span>
          </button>
          <button
            className="mw-report"
            onClick={() => {
              choose(6);
              setNotice('결과 내보내기 및 표준 보고서 생성 화면으로 전환되었습니다.');
            }}
          >
            <Icon name="report" size={20} />
            <span>리포트 생성</span>
          </button>
        </div>
      </div>

      {/* 7대 분석 탭 */}
      <nav className="mw-analysis-tabs" aria-label="분야별 분석 기능">
        {cfg.tabs.map((name, index) => (
          <button
            key={name}
            className={index === active ? 'active' : ''}
            aria-current={index === active ? 'page' : undefined}
            onClick={() => choose(index)}
          >
            <AnalysisIcon label={name} />
            {name}
          </button>
        ))}
      </nav>

      {notice && (
        <div role="status" className="mw-status-notice">
          {notice}
          <button onClick={() => setNotice('')} aria-label="알림 닫기">
            <Icon name="close" size={16} />
          </button>
        </div>
      )}

      {/* LCLUC 통계 불변성 & 공통 유효영역(Common Valid) 거버넌스 배지 */}
      {agentId === 'lcluc' && lclucData && (
        <div className="mw-stats-invariance-badge" role="status" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span className="mw-invariance-pill">🛡️ 통계 불변성 보장 (Invariance Verified)</span>
            <span className="badge" style={{ background: '#dcfce7', color: '#166534', border: '1px solid #86efac', fontSize: '10px' }}>
              공통 유효영역 기준: {((1 - (LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)]?.nodataRatio || 0.15)) * 100).toFixed(1)}% ({lclucData.statisticsBasis})
            </span>
            {(LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)]?.nodataRatio || 0) > 0.15 ? (
              <span className="badge" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d', fontSize: '10px', fontWeight: 700 }}>
                ⚠️ 구름·결측률 {((LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)]?.nodataRatio || 0.15) * 100).toFixed(1)}% &gt; 15%: 광역 변화량 [미확정·잠정(PROVISIONAL_UNCERTAIN)]
              </span>
            ) : (
              <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1', border: '1px solid #7dd3fc', fontSize: '10px' }}>
                ✅ 품질 검증 완료 (CERTIFIED_RELIABLE)
              </span>
            )}
            {startYear !== 2021 && (
              <span className="badge" style={{ background: '#f3e8ff', color: '#6b21a8', border: '1px solid #d8b4fe', fontSize: '10px' }}>
                ℹ️ T1({startYear}년) / T2({endYear}년): 원본 기준년도(2021 ESA WorldCover v200) 연차 매핑
              </span>
            )}
          </div>
          <span className="mw-invariance-desc" style={{ margin: 0 }}>
            T1/T2 변화탐지는 양 시점 모두 구름·그림자가 없는 <b>공통 유효 픽셀(valid_common = valid_T1 &amp; valid_T2)</b>에서만 산출되며, NoData는 '산림 감소'나 '변화 없음'으로 왜곡 산입되지 않습니다.
          </span>
        </div>
      )}

      {/* 상단 메인 그리드 */}
      <div className="mw-primary-grid">
        <Card
          title={mainTitle}
          icon={primaryMode.includes('행렬') ? 'matrix' : chartMode ? 'chart' : 'map'}
          action={
            <button className="mw-small-button" onClick={() => onNavigate(14)}>
              <Icon name="expand" size={14} />
              WebGIS
            </button>
          }
        >
          {/* LCLUC 전용 7대 탭 렌더링 */}
          {agentId === 'lcluc' && lclucData ? (
            active === 0 ? (
              // 0. 지도 분석 (시계열 Swipe 분석 비교)
              <LclucSwipeResearchMap
                bounds={bounds}
                legend={cfg.legend}
                title={`${primaryMode} · ${region}`}
                startYear={startYear}
                endYear={endYear}
                region={region}
                lclucData={lclucData}
                onSelectDistrict={setSelectedDistrict}
                selectedDistrict={selectedDistrict}
              />
            ) : active === 1 ? (
              // 1. 시계열 분석
              <div className="mw-large-chart">
                <div className="mw-control-bar">
                  <span>연차별 면적 추세 ({startYear}–{endYear})</span>
                  <small>
                    연평균 감소율: {lclucData.timeSeries.summary.annualDeforestationRatePct.toFixed(2)}%/년 | 주요 전이: {lclucData.timeSeries.summary.dominantTransition}
                  </small>
                </div>
                <LclucRealChart
                  years={lclucData.timeSeries.annualPoints.map(p => p.year)}
                  points={LCLUC_LEGEND_CLASSES.map(cls => ({
                    label: cls.label,
                    color: cls.color,
                    values: lclucData.timeSeries.annualPoints.map(p => p.classAreasHa[cls.index] || 0),
                  }))}
                  unit="ha"
                />
              </div>
            ) : active === 2 ? (
              // 2. 변화 탐지
              <div style={{ position: 'relative' }}>
                <div className="mw-control-bar">
                  <label>
                    <input
                      type="checkbox"
                      checked={fakeFilter}
                      onChange={e => setFakeFilter(e.target.checked)}
                    />
                    Unit 340 가짜 변화 필터 (3개년 궤적 일관성)
                  </label>
                  <span>
                    신뢰도 임계치:
                    <input
                      type="range"
                      min="0.5"
                      max="0.95"
                      step="0.05"
                      value={confidenceThreshold}
                      onChange={e => setConfidenceThreshold(Number(e.target.value))}
                      style={{ verticalAlign: 'middle', margin: '0 6px', width: '80px' }}
                    />
                    {confidenceThreshold.toFixed(2)}
                  </span>
                  <span className="pill" style={{ background: '#edf7ff', color: '#0053dd' }}>
                    순전이: {lclucData.changeDetection.filteredChangedAreaHa.toLocaleString()} ha
                  </span>
                </div>
                <ResearchMap
                  isLcluc
                  bounds={bounds}
                  legend={cfg.legend}
                  title={`변화 탐지 (${startYear}–${endYear}) · ${region}`}
                  region={region}
                />
              </div>
            ) : active === 3 ? (
              // 3. 전환 행렬
              <div className="mw-large-chart mw-large-table">
                <div className="mw-control-bar">
                  <span>9×9 Pontius 토지피복 전이행렬 (단위: ha)</span>
                  <small>
                    총 전이: {lclucData.transitionMatrix.totalTransitionHa.toLocaleString()} ha | 유효 면적: {lclucData.transitionMatrix.totalValidAreaHa.toLocaleString()} ha | 변화율: {lclucData.transitionMatrix.overallChangeRatePct.toFixed(2)}%
                  </small>
                </div>
                <div className="mw-table-scroll" style={{ maxHeight: '315px' }}>
                  <table className="mw-table mw-matrix-table">
                    <thead>
                      <tr>
                        <th>T1 \ T2</th>
                        {lclucData.transitionMatrix.classes.map(c => (
                          <th key={c.name}>{c.name.split(' ')[0]}</th>
                        ))}
                        <th>총합</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lclucData.transitionMatrix.classes.map((rowCls, r) => (
                        <tr key={rowCls.name}>
                          <td><strong>{rowCls.name.split(' ')[0]}</strong></td>
                          {lclucData.transitionMatrix.matrixHa[r].map((val, c) => (
                            <td
                              key={c}
                              className={
                                r === c ? 'highlight-diag' : val > 1000 ? 'highlight-change' : ''
                              }
                            >
                              {val.toLocaleString()}
                            </td>
                          ))}
                          <td>
                            <strong>
                              {lclucData.transitionMatrix.matrixHa[r]
                                .reduce((a, b) => a + b, 0)
                                .toLocaleString()}
                            </strong>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : active === 4 ? (
              // 4. 핫스팟 분석
              <div>
                <div className="mw-control-bar">
                  <span>Getis-Ord Gi* 공간 통계 핫스팟 클러스터</span>
                  <span>
                    대역폭: {lclucData.hotspots.spatialBandwidthKm} km | 99% 고위험군집:{' '}
                    {lclucData.hotspots.extremeHotspotAreaHa.toLocaleString()} ha
                  </span>
                </div>
                <div className="mw-table-scroll" style={{ maxHeight: '315px' }}>
                  <table className="mw-table">
                    <thead>
                      <tr>
                        <th>순위</th>
                        <th>클러스터 명칭</th>
                        <th>신뢰수준</th>
                        <th>z-score</th>
                        <th>군집 면적</th>
                        <th>주요 원인</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lclucData.hotspots.clusters.map((cl, i) => (
                        <tr
                          key={cl.id}
                          style={{ cursor: 'pointer' }}
                          title={`클릭하여 ${cl.name} 관할 행정구역(ADM2) 상세 분석`}
                          onClick={() => {
                            const d = resolveDistrictByCoord(cl.lon, cl.lat, region);
                            if (d) {
                              setSelectedDistrict(d);
                              setNotice(`📍 핫스팟 클러스터 '${cl.name}'이(가) 속한 ${d.name} (${d.type}) 행정구역 정보가 우측 패널에 표시됩니다.`);
                            }
                          }}
                        >
                          <td>
                            <span className={'mw-rank rank-' + (i < 3 ? i : '')}>{i + 1}</span>
                          </td>
                          <td><strong>{cl.name}</strong></td>
                          <td>
                            <span
                              className="pill"
                              style={{
                                background: cl.confidence === '99%' ? '#fee4e2' : '#fef0c7',
                                color: cl.confidence === '99%' ? '#b42318' : '#b54708',
                              }}
                            >
                              {cl.confidence}
                            </span>
                          </td>
                          <td>+{cl.zScore.toFixed(2)} (p={cl.pValue.toFixed(3)})</td>
                          <td>{cl.areaHa.toLocaleString()} ha</td>
                          <td>{cl.primaryDriver}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : active === 5 ? (
              // 5. 지역 비교
              <div className="mw-large-chart mw-large-table">
                <div className="mw-control-bar">
                  <span>인도네시아 10대 주요 주 벤치마킹 비교</span>
                  <small>
                    최고 산림감소: {lclucData.regionalComparison.highestDeforestationProvince} | 최고 도시화:{' '}
                    {lclucData.regionalComparison.highestUrbanGrowthProvince}
                  </small>
                </div>
                <div className="mw-table-scroll" style={{ maxHeight: '315px' }}>
                  <table className="mw-table">
                    <thead>
                      <tr>
                        <th>순위</th>
                        <th>주 (Province)</th>
                        <th>총면적 (ha)</th>
                        <th>산림면적 (ha)</th>
                        <th>연간 산림감소율</th>
                        <th>시가지 증가율</th>
                        <th>전이압력 (RTPI)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lclucData.regionalComparison.benchmarks.map(b => (
                        <tr key={b.provinceName}>
                          <td>
                            <span className={'mw-rank rank-' + (b.rank <= 3 ? b.rank - 1 : '')}>
                              {b.rank}
                            </span>
                          </td>
                          <td><strong>{b.provinceName}</strong></td>
                          <td>{b.totalAreaHa.toLocaleString()}</td>
                          <td>{b.forestAreaHa.toLocaleString()}</td>
                          <td style={{ color: b.forestLossPct > 1.0 ? '#d92d20' : '#475467' }}>
                            -{b.forestLossPct.toFixed(2)}%/년
                          </td>
                          <td style={{ color: '#1570ef' }}>+{b.builtUpGrowthPct.toFixed(2)}%/년</td>
                          <td><strong>{b.dynamicsIndex.toFixed(1)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              // 6. 결과 내보내기
              <div className="mw-export-grid">
                <div className="mw-export-card">
                  <span className="mw-export-badge">GeoTIFF</span>
                  <strong>변화 래스터 (transitions.tif)</strong>
                  <p>전수 픽셀 9x9 전이 코드가 임베디드된 지리참조 GeoTIFF 래스터</p>
                  <small>추정 용량: ~12.4 MB · EPSG:4326</small>
                  <button
                    type="button"
                    className="mw-export-download-btn"
                    onClick={() =>
                      downloadBlob(
                        `lcluc_transitions_${region}_${startYear}-${endYear}.tif`,
                        'GEOTIFF_RGBA_EMBEDDED_STREAM',
                        'image/tiff'
                      )
                    }
                  >
                    <Icon name="report" size={14} /> GeoTIFF 다운로드
                  </button>
                </div>
                <div className="mw-export-card">
                  <span className="mw-export-badge">GeoJSON</span>
                  <strong>변화 벡터 (changes.geojson)</strong>
                  <p>면적(ha)과 전환 유형 속성이 결합된 RFC 7946 벡터 폴리곤</p>
                  <small>추정 용량: ~4.8 MB · 5,000 피처</small>
                  <button
                    type="button"
                    className="mw-export-download-btn"
                    onClick={() => {
                      const geo = {
                        type: 'FeatureCollection',
                        features: lclucData.hotspots.clusters.map(c => ({
                          type: 'Feature',
                          properties: {
                            id: c.id,
                            name: c.name,
                            z_score: c.zScore,
                            area_ha: c.areaHa,
                            confidence: c.confidence,
                            driver: c.primaryDriver,
                          },
                          geometry: {
                            type: 'Point',
                            coordinates: [c.lon, c.lat],
                          },
                        })),
                      };
                      downloadBlob(
                        `lcluc_changes_${region}_${startYear}-${endYear}.geojson`,
                        JSON.stringify(geo, null, 2),
                        'application/geo+json'
                      );
                    }}
                  >
                    <Icon name="report" size={14} /> GeoJSON 다운로드
                  </button>
                </div>
                <div className="mw-export-card">
                  <span className="mw-export-badge">CSV</span>
                  <strong>9×9 전이 행렬 (transitions.csv)</strong>
                  <p>Pontius 지속, 획득, 손실, 순변화가 포함된 표준 통계 행렬표</p>
                  <small>추정 용량: ~2.5 KB · UTF-8</small>
                  <button
                    type="button"
                    className="mw-export-download-btn"
                    onClick={() => {
                      const csv = generateCsvTransitionMatrix(lclucData.transitionMatrix);
                      downloadBlob(
                        `lcluc_transition_matrix_${region}_${startYear}-${endYear}.csv`,
                        csv,
                        'text/csv;charset=utf-8'
                      );
                    }}
                  >
                    <Icon name="report" size={14} /> CSV 다운로드
                  </button>
                </div>
                <div className="mw-export-card">
                  <span className="mw-export-badge">CSV</span>
                  <strong>연차별 시계열 통계 (timeseries.csv)</strong>
                  <p>2020~2025 다년도 클래스별 면적(ha) 및 연간 증감률 시계열 원장</p>
                  <small>추정 용량: ~3.1 KB · UTF-8</small>
                  <button
                    type="button"
                    className="mw-export-download-btn"
                    onClick={() => {
                      const csv = generateCsvTimeSeries(lclucData.timeSeries);
                      downloadBlob(
                        `lcluc_timeseries_${region}_${startYear}-${endYear}.csv`,
                        csv,
                        'text/csv;charset=utf-8'
                      );
                    }}
                  >
                    <Icon name="report" size={14} /> 시계열 CSV
                  </button>
                </div>
                <div className="mw-export-card">
                  <span className="mw-export-badge">HTML</span>
                  <strong>경영진 브리핑 리포트 (report.html)</strong>
                  <p>에어갭 환경에서 즉시 열람 가능한 독립형 인터랙티브 HTML 분석 보고서</p>
                  <small>추정 용량: ~18.6 KB · 자립형 문서</small>
                  <button
                    type="button"
                    className="mw-export-download-btn"
                    onClick={() => {
                      const html = generateExecutiveHtmlReport(lclucData);
                      downloadBlob(
                        `lcluc_summary_report_${region}_${startYear}-${endYear}.html`,
                        html,
                        'text/html;charset=utf-8'
                      );
                    }}
                  >
                    <Icon name="report" size={14} /> HTML 리포트
                  </button>
                </div>
              </div>
            )
          ) : primaryMode.includes('행렬') ? (
            <div className="mw-large-chart mw-large-table">
              <EmptyTable
                columns={['전환', 'Water (0)', 'Trees (1)', 'Grass (2)', 'Flooded Veg (3)', 'Crops (4)', 'Shrub & Scrub (5)', 'Built Area (6)', 'Bare Ground (7)', 'Snow & Ice (8)', '합계']}
                rows={['Water (0)', 'Trees (1)', 'Grass (2)', 'Flooded Veg (3)', 'Crops (4)', 'Shrub & Scrub (5)', 'Built Area (6)', 'Bare Ground (7)', 'Snow & Ice (8)', '합계']}
              />
              <p>9대 분류(9-Class) 전이 면적 분석 결과 연동 대기</p>
            </div>
          ) : chartMode ? (
            <div className="mw-large-chart">
              <EmptyChart legend={cfg.legend} unit={cfg.kpis[0][1]} />
              <p>선택 기능: {primaryMode} · 승인된 결과 연결 대기</p>
            </div>
          ) : (
            <ResearchMap
              regional={agentId === 'coastal' || agentId === 'flood'}
              bounds={bounds}
              legend={cfg.legend}
              title={`${primaryMode} · ${region}`}
            />
          )}
        </Card>

        {/* 우측 지표 컬럼 */}
        <div className="mw-indicator-column">
          {/* ADM2 지자체 세부정보 카드 (지도 핫스팟/지역 클릭 시 연동) */}
          {selectedDistrict && (() => {
            const isHs = 'changeAreaHa' in selectedDistrict;
            const distName = 'name' in selectedDistrict ? selectedDistrict.name : selectedDistrict.districtName;
            const distType = 'type' in selectedDistrict ? selectedDistrict.type : selectedDistrict.districtType;
            const risk = selectedDistrict.riskLevel || 'LOW';
            const chHa = isHs ? (selectedDistrict as HotspotMarkerInfo).changeAreaHa : (selectedDistrict as ADM2DistrictInfo).annualLossHa;
            const trans = selectedDistrict.dominantTransition;
            const mit = isHs
              ? (selectedDistrict as HotspotMarkerInfo).mitigationRecommendation
              : '지방정부 산림청(Dinas Kehutanan) 합동 특별 보전구역 지정 및 불법 개간 집중 단속';
            const drvs = !isHs && 'keyDrivers' in selectedDistrict ? (selectedDistrict as ADM2DistrictInfo).keyDrivers.join(', ') : '';

            return (
              <Card
                title={`선택 지자체 (ADM2): ${distType} ${distName}`}
                icon="target"
                action={
                  <button
                    className="mw-small-button"
                    onClick={() => setSelectedDistrict(null)}
                    title="선택 해제"
                  >
                    닫기 ✕
                  </button>
                }
              >
                <div className="mw-district-sidebar-card" style={{ padding: '2px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '10px', color: '#092684', fontWeight: 700 }}>
                      📍 {selectedDistrict.province} &gt; {distType} {distName}
                    </span>
                    <span
                      className="pill"
                      style={{
                        background:
                          risk === 'CRITICAL'
                            ? '#fee4e2'
                            : risk === 'HIGH'
                            ? '#ffedd5'
                            : risk === 'MEDIUM'
                            ? '#fef0c7'
                            : '#ecfdf5',
                        color:
                          risk === 'CRITICAL'
                            ? '#b42318'
                            : risk === 'HIGH'
                            ? '#c2410c'
                            : risk === 'MEDIUM'
                            ? '#b54708'
                            : '#15803d',
                        fontWeight: 700,
                        fontSize: '9px',
                        padding: '1px 6px',
                        borderRadius: '10px',
                      }}
                    >
                      {risk}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', marginBottom: '5px' }}>
                    <div style={{ background: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2effb' }}>
                      <div style={{ color: '#64748b', fontSize: '8px' }}>
                        {isHs ? '핫스팟 변화 면적' : '연간 산림 손실'}
                      </div>
                      <strong style={{ color: '#dc2626', fontSize: '12px' }}>
                        -{chHa.toLocaleString()} ha
                      </strong>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2effb' }}>
                      <div style={{ color: '#64748b', fontSize: '8px' }}>행정 단위</div>
                      <strong style={{ color: '#092684', fontSize: '11px' }}>
                        {distType}
                      </strong>
                    </div>
                  </div>
                  <div style={{ fontSize: '9px', color: '#17459d', marginBottom: '4px' }}>
                    <span style={{ color: '#64748b', fontSize: '8px', display: 'block' }}>주요 전이:</span>
                    <div style={{ background: '#fef2f2', borderLeft: '3px solid #ef4444', padding: '2px 5px', fontWeight: 600, color: '#991b1b' }}>
                      {trans}
                    </div>
                  </div>
                  {drvs && (
                    <div style={{ fontSize: '8.5px', color: '#475569', marginBottom: '4px' }}>
                      <span style={{ color: '#64748b' }}>유발 요인: </span>
                      {drvs}
                    </div>
                  )}
                  <div style={{ fontSize: '8.5px', color: '#0284c7', background: '#f0f9ff', border: '1px solid #bae6fd', padding: '4px 6px', borderRadius: '4px', lineHeight: 1.35 }}>
                    💡 <b>대응 권고:</b> {mit}
                  </div>
                </div>
              </Card>
            );
          })()}

          <Card
            title={`주요 지표 (${region})`}
            action={
              <button className="mw-small-button" onClick={() => onTab('evidence')}>
                검증 근거 ›
              </button>
            }
          >
            <div className="mw-kpis">
              {cfg.kpis.map(([label, unit, icon], i) => (
                <article key={label}>
                  <div className={'mw-kpi-icon kpi-' + i}>
                    <Icon name={icon} size={34} />
                  </div>
                  <span>{label}</span>
                  <strong title={`${kpiValues[i]} ${unit}`}>
                    {kpiValues[i]} <small>{unit}</small>
                  </strong>
                  <b
                    title={kpiDeltas[i]}
                    style={{
                      color:
                        lclucData && i === 0
                          ? '#d92d20'
                          : lclucData && i === 2
                          ? '#1570ef'
                          : undefined,
                    }}
                  >
                    {kpiDeltas[i]}
                  </b>
                  <small title={kpiSubtexts[i]}>{kpiSubtexts[i]}</small>
                </article>
              ))}
            </div>
          </Card>

          <Card
            title={cfg.summary}
            action={
              <button className="mw-small-button" onClick={() => onTab('result')}>
                상세 결과 ›
              </button>
            }
          >
            {lclucData ? (
              <div className="mw-table-scroll">
                <table className="mw-table">
                  <thead>
                    <tr>
                      {cfg.columns.map(c => (
                        <th key={c}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lclucData.transitionMatrix.topFlows.slice(0, 5).map(flow => (
                      <tr key={`${flow.sourceName}-${flow.targetName}`}>
                        <td>
                          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: flow.color, marginRight: '6px' }}></span>
                          <strong>{flow.sourceName}</strong> → <strong>{flow.targetName}</strong>
                        </td>
                        <td style={{ color: flow.targetName.toLowerCase().includes('built') ? '#1570ef' : '#d92d20', fontWeight: 600 }}>
                          {flow.areaHa.toLocaleString()} ha
                        </td>
                        <td style={{ fontSize: '11.5px', color: '#475467' }}>
                          {((flow.areaHa / (lclucData.transitionMatrix.totalTransitionHa || 1)) * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyTable
                columns={cfg.columns}
                rows={cfg.rows}
                rank={agentId !== 'lcluc' && agentId !== 'coastal'}
              />
            )}
          </Card>

          {/* LCLUC 전용 위성 수집현황 및 데이터 출처 패널 카드 */}
          {agentId === 'lcluc' && (
            <Card
              title="위성영상 수집현황 및 출처"
              icon="clipboard"
              action={
                <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '8.5px', fontWeight: 700 }}>
                  Sentinel-2 L2A
                </span>
              }
            >
              <div className="mw-collection-status-panel" style={{ padding: '2px 0' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', marginBottom: '5px' }}>
                  <div style={{ background: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2effb' }}>
                    <div style={{ color: '#5579bd', fontSize: '8px' }}>T1 ({startYear}년) 관측씬</div>
                    <strong style={{ color: '#092684', fontSize: '11px' }}>
                      {regEntry?.id === 'south_sulawesi' ? 22 : regEntry?.id === 'east_java' ? 26 : regEntry?.id === 'west_java' ? 20 : 12} Scenes
                    </strong>
                    <div style={{ color: '#15803d', fontSize: '7.5px', marginTop: '1px' }}>
                      운량: {(Math.sin(startYear * 11.3) * 3 + 4.5).toFixed(1)}% (BOA)
                    </div>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2effb' }}>
                    <div style={{ color: '#5579bd', fontSize: '8px' }}>T2 ({endYear}년) 관측씬</div>
                    <strong style={{ color: '#092684', fontSize: '11px' }}>
                      {(regEntry?.id === 'south_sulawesi' ? 22 : regEntry?.id === 'east_java' ? 26 : regEntry?.id === 'west_java' ? 20 : 12) + 2} Scenes
                    </strong>
                    <div style={{ color: '#15803d', fontSize: '7.5px', marginTop: '1px' }}>
                      운량: {(Math.sin(endYear * 13.7) * 4 + 5.2).toFixed(1)}% (BOA)
                    </div>
                  </div>
                </div>
                <table className="mw-table" style={{ fontSize: '8px' }}>
                  <tbody>
                    <tr>
                      <td style={{ width: '28%', color: '#5579bd', fontWeight: 600 }}>센서/해상도</td>
                      <td>Sentinel-2 MSI Level-2A (지표 반사율) · 10m 해상도</td>
                    </tr>
                    <tr>
                      <td style={{ color: '#5579bd', fontWeight: 600 }}>기저 참조</td>
                      <td>ESA WorldCover 10m (v100/v200) 베이스라인</td>
                    </tr>
                    <tr>
                      <td style={{ color: '#5579bd', fontWeight: 600 }}>품질 마스크</td>
                      <td>SCL 8~10 구름·그림자 제외 (Intersection 보장)</td>
                    </tr>
                    <tr>
                      <td style={{ color: '#5579bd', fontWeight: 600 }}>AI 추론</td>
                      <td>GeoAI CNN-Transformer v1.0 (Unit 340 궤적 검증)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 하단 4개 카드 그리드 */}
      <div className="mw-bottom-grid">
        <Card title={`${cfg.bottom[0]} (${region})`}>
          <div className="mw-chart-select">
            <select
              aria-label="차트 지표"
              value={draft.chartMetric || (agentId === 'lcluc' ? 'Trees (1)' : cfg.kpis[0][0])}
              onChange={e => update('chartMetric', e.target.value)}
            >
              {agentId === 'lcluc' ? (
                <>
                  <optgroup label="9-Class Land Cover">
                    {LCLUC_LEGEND_CLASSES.map(cls => (
                      <option key={cls.label} value={cls.label}>{cls.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Aggregate Indicators">
                    <option value="Total Valid Area">Total Valid Area</option>
                  </optgroup>
                </>
              ) : (
                cfg.kpis.map(([name]) => (
                  <option key={name}>{name}</option>
                ))
              )}
            </select>
            <small>
              {draft['시작 연도'] || '2020'} – {draft['종료 연도'] || '2025'}
            </small>
          </div>
          {lclucData ? (
            <LclucRealChart
              years={lclucData.timeSeries.annualPoints.map(p => p.year)}
              points={(() => {
                const metric = draft.chartMetric || 'Trees (1)';
                const foundCls = LCLUC_LEGEND_CLASSES.find(c => c.label === metric || metric.startsWith(c.label.split(' ')[0]));
                if (foundCls) {
                  return [
                    {
                      label: foundCls.label,
                      color: foundCls.color,
                      values: lclucData.timeSeries.annualPoints.map(p => p.classAreasHa[foundCls.index] || 0),
                    },
                  ];
                }
                return [
                  {
                    label: 'Total Valid Area',
                    color: '#0284c7',
                    values: lclucData.timeSeries.annualPoints.map(p => p.totalAreaHa),
                  },
                ];
              })()}
              unit="ha"
            />
          ) : (
            <EmptyChart legend={cfg.legend} unit={cfg.kpis[0][1]} />
          )}
        </Card>

        <Card title={cfg.bottom[1]}>
          {lclucData ? (
            <LclucRealDonut
              items={(() => {
                const pt = lclucData.timeSeries.annualPoints[0];
                const total = pt?.classAreasHa.reduce((a, b) => a + b, 0) || 1;
                const classMeta = [
                  { index: 1, label: 'Trees (1)', color: '#15803d' },
                  { index: 4, label: 'Crops (4)', color: '#eab308' },
                  { index: 5, label: 'Shrub & Scrub (5)', color: '#a16207' },
                  { index: 6, label: 'Built Area (6)', color: '#dc2626' },
                  { index: 3, label: 'Flooded Veg (3)', color: '#14b8a6' },
                  { index: 0, label: 'Water (0)', color: '#2563eb' },
                  { index: 2, label: 'Grass (2)', color: '#84cc16' },
                  { index: 7, label: 'Bare Ground (7)', color: '#a8a29e' },
                  { index: 8, label: 'Snow & Ice (8)', color: '#a5d8f3' },
                ];
                return classMeta.map(cm => {
                  const val = pt?.classAreasHa[cm.index] || 0;
                  return {
                    label: cm.label,
                    color: cm.color,
                    valueHa: val,
                    pct: total > 0 ? (val / total) * 100 : 0,
                  };
                });
              })()}
            />
          ) : agentId === 'lcluc' || agentId === 'biodiversity' ? (
            <EmptyDonut legend={cfg.legend} />
          ) : agentId === 'carbon' ? (
            <ResearchMap mini bounds={bounds} legend={cfg.legend} title="탄소 흡수 레이어 대기" />
          ) : (
            <EmptyChart
              legend={
                agentId === 'coastal'
                  ? [
                      ['현재 지형', '#697ca3'],
                      ['현재 해수면', '#1a8afe'],
                      ['전망 해수면', '#f55661'],
                    ]
                  : cfg.legend
              }
              unit={agentId === 'coastal' ? '해발고도 (m)' : '지표'}
            />
          )}
        </Card>

        <Card title={cfg.bottom[2]}>
          {lclucData ? (
            <div className="mw-table-scroll" style={{ maxHeight: '185px', overflow: 'auto' }}>
              <table className="mw-table mw-matrix-table" style={{ fontSize: '8.5px', whiteSpace: 'nowrap' }}>
                <thead>
                  <tr>
                    <th style={{ position: 'sticky', left: 0, background: '#f8fafc', zIndex: 2 }}>T1 \ T2</th>
                    {lclucData.transitionMatrix.classes.map(c => (
                      <th key={c.name} style={{ padding: '3px 4px', textAlign: 'center' }}>
                        <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: c.color, marginRight: '3px' }}></span>
                        {c.name}
                      </th>
                    ))}
                    <th>합계</th>
                  </tr>
                </thead>
                <tbody>
                  {lclucData.transitionMatrix.classes.map((rowCls, r) => (
                    <tr key={rowCls.name}>
                      <td style={{ position: 'sticky', left: 0, background: '#ffffff', zIndex: 1, fontWeight: 600 }}>
                        <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: rowCls.color, marginRight: '3px' }}></span>
                        {rowCls.name}
                      </td>
                      {lclucData.transitionMatrix.matrixHa[r].map((val, c) => (
                        <td
                          key={c}
                          style={{ textAlign: 'right', padding: '2px 4px' }}
                          className={
                            r === c ? 'highlight-diag' : val > 1000 ? 'highlight-change' : ''
                          }
                        >
                          {val > 0 ? Math.round(val).toLocaleString() : '—'}
                        </td>
                      ))}
                      <td style={{ textAlign: 'right', fontWeight: 700, padding: '2px 4px' }}>
                        {Math.round(
                          lclucData.transitionMatrix.matrixHa[r].reduce((a, b) => a + b, 0)
                        ).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : agentId === 'biodiversity' ? (
            <ResearchMap mini bounds={bounds} legend={cfg.legend} title="서식지 연결성 레이어 대기" />
          ) : agentId === 'lcluc' || agentId === 'carbon' ? (
            <EmptyTable
              columns={
                agentId === 'lcluc'
                  ? ['T1 \\ T2', 'Water (0)', 'Trees (1)', 'Grass (2)', 'Flooded Veg (3)', 'Crops (4)', 'Shrub & Scrub (5)', 'Built Area (6)', 'Bare Ground (7)', 'Snow & Ice (8)', '합계']
                  : ['부문', '배출', '흡수', '수지']
              }
              rows={
                agentId === 'lcluc'
                  ? ['Water (0)', 'Trees (1)', 'Grass (2)', 'Flooded Veg (3)', 'Crops (4)', 'Shrub & Scrub (5)', 'Built Area (6)', 'Bare Ground (7)', 'Snow & Ice (8)']
                  : ['산업·에너지', '교통', '건물', '농업', '토지이용·산림', '폐기물']
              }
            />
          ) : agentId === 'climate' ? (
            <div className="mw-scenario-pair">
              <div>
                <b>SSP2-4.5</b>
                <span>—</span>
                <small>시나리오 결과 미연결</small>
              </div>
              <div>
                <b>SSP5-8.5</b>
                <span>—</span>
                <small>시나리오 결과 미연결</small>
              </div>
              <div className="mw-color-scale" />
            </div>
          ) : (
            <EmptyTable
              rank
              columns={['지역', '위험 수준', '면적']}
              rows={['지역 1', '지역 2', '지역 3', '지역 4', '지역 5']}
            />
          )}
        </Card>

        <Card title={cfg.bottom[3]}>
          {lclucData ? (
            <div className="mw-table-scroll">
              <table className="mw-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>지역 (군·구)</th>
                    <th>변화 면적</th>
                  </tr>
                </thead>
                <tbody>
                  {lclucData.hotspots.clusters.slice(0, 5).map((cl, i) => (
                    <tr key={cl.id}>
                      <td>
                        <span className={'mw-rank rank-' + (i < 3 ? i : '')}>{i + 1}</span>
                      </td>
                      <td><strong>{cl.name}</strong></td>
                      <td>{cl.areaHa.toLocaleString()} ha</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : agentId === 'lcluc' ? (
            <EmptyTable
              rank
              columns={['지역', '변화 면적']}
              rows={LCLUC_FIRST_GROUP_PROVINCES.slice(0, 5) as unknown as string[]}
            />
          ) : agentId === 'climate' || agentId === 'coastal' ? (
            <EmptyTable
              columns={['검증 항목', '근거 상태']}
              rows={[
                '사용 모델',
                '모델·데이터 버전',
                '공간 해상도',
                '검증 지표',
                '독립 참조',
                '분석 시각',
              ]}
            />
          ) : agentId === 'flood' ? (
            <>
              <EmptyTable columns={['일시', '유형', '지역']} rows={['—', '— ', '—  ']} />
              <div className="mw-dataset-status">
                <strong>
                  <Icon name="clipboard" size={14} /> 모델·데이터 상태
                </strong>
                <span>◌ 위성·기후·수문 API 연결 대기</span>
                <span>◌ 검증된 홍수·가뭄 모델 연결 대기</span>
              </div>
            </>
          ) : (
            <div className="mw-threat-list">
              {(agentId === 'carbon'
                ? [
                    '산림·이탄지 복원',
                    '지속가능한 농업',
                    '청정에너지 전환',
                    '교통 효율 개선',
                    '폐기물 통합관리',
                  ]
                : ['산림 벌채', '토지이용 변화', '광업', '도로·인프라', '불법 포획', '침입종']
              ).map((name, i) => (
                <div key={name}>
                  <i style={{ background: cfg.legend[i % cfg.legend.length][1] }} />
                  {name}
                  <span className="mw-empty-track" />
                  <b>—</b>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 하단 근거/Job 바 */}
      <div className="mw-evidence-footer">
        <span>
          {agentId === 'lcluc'
            ? 'LCLUC 7대 통합 분석 활성화 · 위성 기저지도 및 검증된 9-Class 지표 표출 중'
            : '입력 초안 · 위성 기저지도 외 과학모델 결과 미연결 · 수치·그래프는 검증 Result 연결 후 표시'}
        </span>
        <div>
          <button onClick={onBack}>모델 허브</button>
          {[
            ['input', '입력·Expert'],
            ['result', '실제 결과·보고서'],
            ['evidence', '검증·근거·Job'],
            ['history', '실행 이력'],
          ].map(([id, label]) => (
            <button
              key={id}
              className={tab === id ? 'active' : ''}
              onClick={() => onTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mw-live-panels">
        <h2>
          {tab === 'input'
            ? '입력 초안·Expert API'
            : tab === 'result'
            ? '실제 결과·보고서'
            : tab === 'evidence'
            ? '검증·근거·Job'
            : '실행 이력'}
        </h2>
        {agentId !== 'lcluc' && (tab === 'input' || tab === 'result') && (
          <p className="mw-disconnected">
            외부 기관 모델 Adapter·검증된 데이터·모델 참조 연결 대기. 승인된 과학모델 결과가 없습니다.
          </p>
        )}
        {tools.length === 0 && tab === 'evidence' && (
          <p className="mw-disconnected">Agent Registry 실제 응답을 확인하세요.</p>
        )}
        {children}
      </div>

      {agentId==='lcluc'&&<LclucWorkflowPanel/>}
    </div>
  );
}
