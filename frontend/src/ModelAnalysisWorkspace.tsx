import { Fragment as ReactFragment, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl';
import type { EvidenceRecord } from './integrationAdapter';
import './model-workspace.css';
import AnalysisIcon from './AnalysisIcon';
import { Icon } from './Icon';
import LclucWorkflowPanel from './LclucWorkflowPanel';
import LclucAnnualIntake from './LclucAnnualIntake';
import { SentinelAnalysisPanel, SentinelLayerControls, sentinelMarkers, sentinelYearAsset, useSentinelExplorer } from './LclucSentinelExplorer';
import type { SentinelExplorer } from './LclucSentinelExplorer';
import { SentinelResult, sentinelResultTitles } from './LclucSentinelResults';
import type { SentinelResultId } from './LclucSentinelResults';
import { LandsatInventory, LandsatLayerControls, LandsatLongChange, LandsatLongTrend,
  landsatAsset, useLandsatExplorer } from './LclucLandsatExplorer';
import LclucModelComparison from './LclucModelComparison';
import LclucBantenAreaComparison from './LclucBantenAreaComparison';
import type { LandsatExplorer } from './LclucLandsatExplorer';
import { useBantenComparison } from './bantenProvinceComparison';
import type { Hotspot } from './bantenProvinceComparison';
import { ha, readBantenLandCover, useLclucExplorer } from './lclucExplorerData';
import type { AdminBoundary, ExplorerCase, ExplorerImagery, ProvinceLandCover } from './lclucExplorerData';
import {
  adminBoundaryStartLayer, afterAdminStyle, allAdminBoundaries, drawAdminBoundaries, showAdminBoundaries,
} from './adminBoundaryMap';
import { resultReviewHash } from './institutionOpsClient';
import { LCLUC_POSTPROCESS_STEP } from './catalogNavigation';
import {
  LCLUC_FIRST_GROUP_PROVINCES,
  LCLUC_FIRST_GROUP_REGIONS,
  LCLUC_PROVINCE_REGISTRY,
  sanitizeLclucProvince,
  isFirstGroupProvince,
  createLclucRasterSourceSpec,
  inspectPixelAtCoord,
  type PixelInspectionResult,
} from './lclucWmsRasterAdapter';
import {
  type HotspotMarkerInfo,
  type ADM2DistrictInfo,
} from './LclucHotspotDistrictResolver';

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
      ['수목 면적 (Trees)', 'ha', 'forest'],
      ['시가화 면적 (Built Area)', 'ha', 'buildings'],
      ['농경지 면적 (Crops)', 'ha', 'crops'],
      ['총 유효 분석 면적', 'ha', 'area'],
    ],
    summary: '주요 토지피복 전이 요약',
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
  lcluc: 'Banten',
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

    const removeAdmin = showAdminBoundaries(map);
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(node.current);
    return () => {
      removeAdmin();
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

// The original Workspace map and controls use exact-year, hash-checked overlays.
const ESRI_CLASS_NAMES: Record<number, string> = {
  1: 'Water', 2: 'Trees', 4: 'Flooded vegetation', 5: 'Crops', 7: 'Built area',
  8: 'Bare ground', 9: 'Snow/ice', 11: 'Rangeland',
};

const imageryUse: Record<ExplorerImagery['id'], { files: string; purpose: string }> = {
  'sentinel-2': { files: 'B02·B03·B04·B08·B11·B12 + SCL', purpose: '관측 영상 비교' },
  landsat: { files: 'SR_B2–SR_B7 + QA_PIXEL', purpose: '관측 영상 비교' },
  disaster: { files: 'NASA Earth Observatory 발행 JPEG 2장', purpose: '사건 전후 시각 판독' },
};

function LclucChangePreviewMap({ url, bounds, hotspots }: { url: string; bounds: Bounds; hotspots?: Hotspot[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [mapUnavailable, setMapUnavailable] = useState(false);
  const [w, s, e, n] = bounds;
  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container,
        style: {
          version: 8,
          sources: { change: { type: 'image', url, coordinates: [[w, n], [e, n], [e, s], [w, s]] } },
          layers: [
            { id: 'change-background', type: 'background', paint: { 'background-color': '#263e4c' } },
            { id: 'change-raster', type: 'raster', source: 'change', paint: { 'raster-resampling': 'nearest' } },
          ],
        },
        bounds: [[w, s], [e, n]], fitBoundsOptions: { padding: 24 }, attributionControl: false,
      });
    } catch {
      setMapUnavailable(true);
      return;
    }
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
    map.addControl(new maplibregl.AttributionControl({ customAttribution: '주·군·시 경계 One Map / BIG' }));
    let initiallyFitted = false;
    const size = new ResizeObserver(() => {
      if (!container.clientWidth || !container.clientHeight) return;
      map.resize();
      if (!initiallyFitted) {
        initiallyFitted = true;
        map.fitBounds([[w, s], [e, n]], { padding: 24, duration: 0 });
      }
    });
    size.observe(container);
    const removeAdmin = showAdminBoundaries(map);
    const addHotspots = () => {
      if (!hotspots?.length) return;
      map.addSource('banten-hotspots', { type: 'geojson', data: {
        type: 'FeatureCollection',
        features: hotspots.map(row => ({ type: 'Feature', geometry: row.geometry,
          properties: { rank: row.rank } })),
      }});
      map.addLayer({ id: 'banten-hotspot-cells', type: 'line', source: 'banten-hotspots',
        paint: { 'line-color': '#99f6e4', 'line-width': 2.2 } });
      map.addLayer({ id: 'banten-hotspot-rank', type: 'symbol', source: 'banten-hotspots',
        layout: { 'text-field': ['to-string', ['get', 'rank']], 'text-font': ['Arial Bold'], 'text-size': 12 },
        paint: { 'text-color': '#102e3b', 'text-halo-color': '#f0fdfa', 'text-halo-width': 2 } });
    };
    const removeHotspots = afterAdminStyle(map, addHotspots);
    return () => { size.disconnect(); removeHotspots(); removeAdmin(); map.remove(); };
  }, [url, w, s, e, n, hotspots]);
  return mapUnavailable
    ? <img className="mw-lcluc-result-image" src={url} alt="공통 유효 범위에서 달라진 토지피복"/>
    : <div className="mw-lcluc-result-map" ref={ref} aria-label="행정경계를 포함한 토지피복 변화 지도"/>;
}

const SWIPE_AUTO_PLAY_MS = 5000;
type SwipePlayback =
  | { state: 'playing'; startedAt: number }
  | { state: 'paused'; elapsed: number }
  | { state: 'finished' };

function LclucSwipeResearchMap({ bounds, region, startYear, endYear, detail, imagery, status, provinceView, onProvinceView,
  explorer, landsat, yearOptions, layer, setLayer, downloadsId, onShowMap, onYearChange }: {
  bounds: Bounds;
  region: string;
  startYear: number;
  endYear: number;
  detail?: ExplorerCase;
  imagery: ExplorerImagery[];
  status: string;
  provinceView: boolean;
  onProvinceView: (whole: boolean) => void;
  explorer: SentinelExplorer;
  landsat: LandsatExplorer;
  yearOptions: string[];
  layer: string;
  setLayer: (layer: string) => void;
  downloadsId: string;
  onShowMap: () => void;
  onYearChange: (side: 'start' | 'end', value: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const leftMap = useRef<maplibregl.Map | null>(null);
  const rightMap = useRef<maplibregl.Map | null>(null);
  const [position, setPosition] = useState(50);
  const [mode, setMode] = useState<'swipe' | 'animate' | 'single'>('swipe');
  const [play, setPlay] = useState(false);
  const [swipePlayback, setSwipePlayback] = useState<SwipePlayback>();
  const [swipeSeconds, setSwipeSeconds] = useState(SWIPE_AUTO_PLAY_MS / 1000);
  const [laterFrame, setLaterFrame] = useState(false);
  const [archiveFrame, setArchiveFrame] = useState<number>();
  const [speed, setSpeed] = useState(1500);
  const [opacity, setOpacity] = useState(1);
  const [showBoundary, setShowBoundary] = useState(true);
  const [provinceSelected, setProvinceSelected] = useState(provinceView);
  useEffect(() => setProvinceSelected(provinceView), [provinceView]);
  const [provinceData, setProvinceData] = useState<ProvinceLandCover>();
  const [provinceDataError, setProvinceDataError] = useState(false);
  const [heldBoundary, setHeldBoundary] = useState<AdminBoundary>();
  const [boundaryError, setBoundaryError] = useState(false);
  const [boundaryName, setBoundaryName] = useState('');
  const [showQualityMask, setShowQualityMask] = useState(false);
  useEffect(() => {
    setPosition(50);
    setSwipePlayback(undefined);
    setPlay(false);
    setLaterFrame(false);
    setArchiveFrame(undefined);
  }, [startYear, endYear]);
  const [classFilter, setClassFilter] = useState<string[]>();
  const [mapFallback, setMapFallback] = useState(false);
  const [filtered, setFiltered] = useState<{ key: string; urls: [string | undefined, string | undefined] }>();
  const reg = LCLUC_PROVINCE_REGISTRY[sanitizeLclucProvince(region)];
  const boundary = heldBoundary;
  const provinceName = boundary?.geojson.features.find(feature => feature.properties.level === 'province'
    && feature.properties.province_id === reg?.id)?.properties.name;
  const fullBanten = reg?.id === 'banten' && provinceSelected;
  const options = imagery.filter(series => series.id === 'disaster' || (!fullBanten && detail &&
    series.region === reg?.id && Number(series.earlier.observed_on.slice(0, 4)) === startYear
      && Number(series.later.observed_on.slice(0, 4)) === endYear
  ));
  const source = options.find(item => item.id === layer);
  const isDisaster = source?.id === 'disaster';
  const labels = [source?.earlier.observed_on ?? String(startYear), source?.later.observed_on ?? String(endYear)];
  const provinceMode = fullBanten && !isDisaster;
  const opticalSensor = provinceMode && (layer === 'sentinel-2' || layer === 'landsat') ? layer : undefined;
  const sentinel = { ...explorer, active: opticalSensor === 'sentinel-2' };
  const enhancedSentinel = sentinel.active && sentinel.bothSpectral;
  const archiveYears = useMemo(() => landsat.active
    ? landsat.catalog?.annual.map(item => item.period[0]).filter(year => startYear <= year && year <= endYear) ?? []
    : [], [landsat.active, landsat.catalog, startYear, endYear]);
  const enhancedLandsat = archiveYears.includes(startYear) && archiveYears.includes(endYear);
  const opticalTitles = { 'sentinel-2': 'Sentinel-2 L2A', landsat: 'Landsat C2 L2' };
  const opticalYears = opticalSensor ? provinceData?.optical?.[opticalSensor] : undefined;
  const provinceFirst = enhancedSentinel ? sentinelYearAsset(startYear, sentinel.spectral)
    : enhancedLandsat ? landsatAsset(startYear, landsat.layer)
    : opticalSensor ? opticalYears?.[startYear]?.preview : provinceData?.years[startYear];
  const provinceLast = enhancedSentinel ? sentinelYearAsset(endYear, sentinel.spectral)
    : enhancedLandsat ? landsatAsset(endYear, landsat.layer)
    : opticalSensor ? opticalYears?.[endYear]?.preview : provinceData?.years[endYear];
  const esri = source ? undefined : detail?.esri_display;
  const colors = provinceMode ? opticalSensor ? undefined : provinceData?.colors : esri?.colors;
  const cloudColor = colors?.[10];
  const first = provinceMode ? provinceFirst : source?.earlier.preview ?? esri?.earlier ?? detail?.previews['earlier-preview'];
  const last = provinceMode ? provinceLast : source?.later.preview ?? esri?.later ?? detail?.previews['later-preview'];
  const hasData = Boolean(first && last);
  const sample = detail?.report.grid.bounds_crs84;
  const camera = provinceMode ? reg!.provinceBbox : provinceView ? bounds : sample ?? bounds;
  const overlayBounds = provinceMode ? provinceData?.bounds ?? camera : sample ?? bounds;
  const missingYears = [!provinceFirst ? startYear : null, !provinceLast ? endYear : null].filter(year => year !== null);
  const layerStatus = provinceMode
    ? provinceDataError ? '반텐주 연차 자료 조회 실패'
      : `반텐주 ${opticalSensor ? opticalTitles[opticalSensor] : 'Esri'} ${landsat.active && landsat.catalog ? landsat.catalog.annual.length : Object.keys((opticalSensor ? opticalYears : provinceData?.years) ?? {}).length}개 연도 발행 · ${missingYears.join(', ')}년 준비 중`
    : status;
  useEffect(() => {
    if (!provinceMode) return;
    const abort = new AbortController();
    setProvinceDataError(false);
    function reload() {
      void readBantenLandCover(abort.signal).then(data => {
        if (!abort.signal.aborted) {
          setProvinceData(data);
          setProvinceDataError(false);
        }
      }).catch(() => { if (!abort.signal.aborted) setProvinceDataError(true); });
    }
    reload();
    const timer = window.setInterval(reload, 60000);
    return () => { window.clearInterval(timer); abort.abort(); };
  }, [provinceMode]);
  const maskColors = source || opticalSensor ? undefined : classFilter;
  const maskKey = (maskColors || cloudColor || showQualityMask) && (first || last) && !isDisaster && !opticalSensor
    ? `${maskColors?.join(',') ?? '*'}|${showQualityMask}|${first}|${last}` : '';
  const legendClasses = provinceMode
    ? Object.entries(colors ?? {}).flatMap(([code, color]) => {
      const classCode = Number(code);
      const entry = ESRI_CLASS_NAMES[classCode];
      return classCode === 10 || !entry ? [] : [{ code: classCode, color, name: entry }];
    })
    : detail?.report.classes.map(item => ({ ...item, color: esri?.colors[item.code] ?? item.color })) ?? [];
  const legendRows = cloudColor
    ? [...legendClasses, { code: 10, name: 'Clouds', color: cloudColor }].sort((a, b) => a.code - b.code)
    : legendClasses;
  const leftSource = maskKey ? filtered?.key === maskKey ? filtered.urls[0] : undefined : first;
  const rightSource = maskKey ? filtered?.key === maskKey ? filtered.urls[1] : undefined : last;
  const archivePlaying = mode === 'animate' && enhancedLandsat;
  const visibleArchiveYear = archiveFrame != null && archiveYears.includes(archiveFrame) ? archiveFrame : startYear;
  const shownOnLeft = archivePlaying ? landsatAsset(visibleArchiveYear, landsat.layer)
    : mode === 'animate' && laterFrame ? rightSource : leftSource;
  const leftYear = archivePlaying ? visibleArchiveYear : mode === 'animate' && laterFrame ? endYear : startYear;
  const leftCover = sentinel.active && sentinel.cover ? provinceData?.years[leftYear] : undefined;
  const rightCover = sentinel.active && sentinel.cover ? provinceData?.years[endYear] : undefined;
  const leftQuality = enhancedSentinel && sentinel.quality ? sentinelYearAsset(leftYear, 'quality') : undefined;
  const rightQuality = enhancedSentinel && sentinel.quality ? sentinelYearAsset(endYear, 'quality') : undefined;
  const changeOverlay = sentinel.active && sentinel.change && sentinel.canChange
    ? sentinel.transitionUrl ?? sentinel.changeUrl + '/overlay'
    : enhancedLandsat && landsat.change ? landsat.changeUrl(startYear, endYear) : undefined;
  const leftChange = mode === 'single' || (mode === 'animate' && laterFrame) ? changeOverlay : undefined;

  useEffect(() => {
    if (!maskKey) return;
    let alive = true;
    const rgb = maskColors && new Set(maskColors.map(color => parseInt(color.slice(1), 16)));
    const cloudRgb = cloudColor && parseInt(cloudColor.slice(1), 16);
    async function mask(url: string | undefined) {
      if (!url) return;
      const image = new Image();
      image.src = url;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas unavailable');
      ctx.drawImage(image, 0, 0);
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = pixels.data;
      for (let i = 0; i < d.length; i += 4) {
        if (!d[i + 3]) {
          if (!cloudColor && showQualityMask) {
            d[i] = 245; d[i + 1] = 158; d[i + 2] = 11; d[i + 3] = 190;
          }
          continue;
        }
        const color = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2];
        if (color === cloudRgb ? !showQualityMask : rgb && !rgb.has(color)) d[i + 3] = 0;
      }
      ctx.putImageData(pixels, 0, 0);
      return canvas.toDataURL('image/png');
    }
    Promise.all([mask(first), mask(last)]).then(urls => { if (alive) setFiltered({ key: maskKey, urls }); }).catch(() => {});
    return () => { alive = false; };
  }, [maskKey, first, last, maskColors, cloudColor, showQualityMask]);

  useEffect(() => {
    if (!play || !hasData || mode !== 'animate') return;
    if (!enhancedLandsat) {
      const timer = window.setInterval(() => setLaterFrame(value => !value), speed);
      return () => window.clearInterval(timer);
    }
    const next = archiveYears[archiveYears.indexOf(visibleArchiveYear) + 1];
    if (next == null) return;
    const timer = window.setTimeout(() => {
      setArchiveFrame(next);
      if (next === endYear) setPlay(false);
    }, speed);
    return () => window.clearInterval(timer);
  }, [play, hasData, mode, speed, enhancedLandsat, archiveYears, visibleArchiveYear, endYear]);

  useEffect(() => { setSwipePlayback(undefined); }, [first, last]);

  useEffect(() => {
    if (mode !== 'swipe' || !hasData || swipePlayback?.state !== 'playing') return;
    const { startedAt } = swipePlayback;
    let frame: number;
    function tick(now: number) {
      const remaining = Math.min(SWIPE_AUTO_PLAY_MS, Math.max(0, SWIPE_AUTO_PLAY_MS - (now - startedAt)));
      setSwipeSeconds(Math.ceil(remaining / 1000));
      if (remaining === 0) {
        setPosition(50);
        setSwipePlayback({ state: 'finished' });
        return;
      }
      // One constant-speed sweep follows 50 → 85 → 15 → 50.
      const travelled = 140 * (1 - remaining / SWIPE_AUTO_PLAY_MS);
      const split = travelled <= 35 ? 50 + travelled : travelled <= 105 ? 120 - travelled : travelled - 90;
      setPosition(Math.round(split));
      frame = window.requestAnimationFrame(tick);
    }
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [swipePlayback, hasData, mode]);

  useEffect(() => {
    if (isDisaster || !leftRef.current || !rightRef.current || !containerRef.current) return;
    const style: maplibregl.StyleSpecification = {
      version: 8,
      sources: { imagery: { type: 'raster', tileSize: 256, attribution: 'Tiles © Esri', tiles: [
        'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ] } },
      layers: [{ id: 'base-background', type: 'background', paint: { 'background-color': '#0d3a55' } },
        { id: 'imagery', type: 'raster', source: 'imagery' }],
    };
    const [w, s, e, n] = camera;
    const create = (container: HTMLDivElement) => new maplibregl.Map({
      container, style, bounds: [[w, s], [e, n]], fitBoundsOptions: { padding: 26 }, attributionControl: false,
    });
    let a: maplibregl.Map | undefined;
    let b: maplibregl.Map | undefined;
    try {
      a = create(leftRef.current);
      b = create(rightRef.current);
    } catch {
      a?.remove();
      b?.remove();
      setMapFallback(true);
      return;
    }
    const mapA = a;
    const mapB = b;
    leftMap.current = mapA;
    rightMap.current = mapB;
    setMapFallback(false);
    let syncing = false;
    function sync(from: maplibregl.Map, to: maplibregl.Map) {
      if (syncing) return;
      syncing = true;
      to.jumpTo({ center: from.getCenter(), zoom: from.getZoom(), bearing: from.getBearing(), pitch: from.getPitch() });
      syncing = false;
    }
    mapA.on('move', () => sync(mapA, mapB));
    mapB.on('move', () => sync(mapB, mapA));
    const observer = new ResizeObserver(() => { mapA.resize(); mapB.resize(); sync(mapA, mapB); });
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      mapA.remove(); mapB.remove();
      leftMap.current = null; rightMap.current = null;
    };
  }, [camera, isDisaster]);

  useEffect(() => {
    if (isDisaster) return;
    const [w, s, e, n] = overlayBounds;
    const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [[w, n], [e, n], [e, s], [w, s]];
    const mapSources = [[leftMap.current, shownOnLeft], [rightMap.current, rightSource]] as const;
    const updates = mapSources.map(([map, url]) => {
      if (!map) return () => {};
      const draw = () => {
        if (map.getLayer('verified-observation')) map.removeLayer('verified-observation');
        if (map.getSource('verified-observation')) map.removeSource('verified-observation');
        if (!url) return;
        map.addSource('verified-observation', { type: 'image', url, coordinates });
        map.addLayer({ id: 'verified-observation', type: 'raster', source: 'verified-observation',
          paint: { 'raster-resampling': 'nearest', 'raster-opacity': opacity, 'raster-fade-duration': 0 } },
          ['sentinel-cover', 'sentinel-quality', 'sentinel-change', adminBoundaryStartLayer, 'sentinel-aoi-fill']
            .find(id => map.getLayer(id)));
      };
      if (map.getLayer('base-background')) draw();
      else map.once('load', draw);
      return () => { map.off('load', draw); };
    });
    return () => updates.forEach(remove => remove());
  }, [camera, overlayBounds, shownOnLeft, rightSource, isDisaster, opacity]);

  useEffect(() => {
    const cleanups = [leftMap.current, rightMap.current].flatMap(map => map ? [
      afterAdminStyle(map, () => {
        if (map.getLayer('imagery')) map.setLayoutProperty('imagery', 'visibility', landsat.active ? 'none' : 'visible');
      }),
    ] : []);
    return () => cleanups.forEach(cleanup => cleanup());
  }, [camera, isDisaster, landsat.active]);

  useEffect(() => {
    if (!sentinel.active && !landsat.active) return;
    const [w, s, e, n] = overlayBounds;
    const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [[w, n], [e, n], [e, s], [w, s]];
    const overlays = [
      { map: leftMap.current, sources: [leftCover, leftQuality, leftChange] },
      { map: rightMap.current, sources: [rightCover, rightQuality, changeOverlay] },
    ];
    const cleanups = overlays.flatMap(({ map, sources }) => {
      if (!map) return [];
      const ids = ['sentinel-cover', 'sentinel-quality', 'sentinel-change'];
      const clear = () => {
        if (!map.getStyle()) return;
        for (const id of ids) {
          if (map.getLayer(id)) map.removeLayer(id);
          if (map.getSource(id)) map.removeSource(id);
        }
      };
      const cancel = afterAdminStyle(map, () => {
        clear();
        const before = [adminBoundaryStartLayer, 'sentinel-aoi-fill'].find(id => map.getLayer(id));
        sources.forEach((url, index) => {
          if (!url) return;
          const id = ids[index];
          map.addSource(id, { type: 'image', url, coordinates });
          map.addLayer({ id, type: 'raster', source: id, paint: {
            'raster-opacity': [0.48, 0.85, 0.86][index] * opacity,
            'raster-resampling': 'nearest', 'raster-fade-duration': 0,
          } }, before);
        });
      });
      return [cancel, clear];
    });
    return () => cleanups.forEach(cleanup => cleanup());
  }, [sentinel.active, landsat.active, camera, overlayBounds, leftCover, rightCover, leftQuality, rightQuality, leftChange, changeOverlay, opacity]);

  useEffect(() => {
    if (!sentinel.active) return;
    const maps = [leftMap.current, rightMap.current].filter((map): map is maplibregl.Map => map !== null);
    const onClick = ({ lngLat }: MapMouseEvent) => sentinel.click([lngLat.lng, lngLat.lat]);
    for (const map of maps) {
      map.getCanvas().style.cursor = sentinel.tool ? 'crosshair' : '';
      map.on('click', onClick);
    }
    return () => { for (const map of maps) { map.off('click', onClick); map.getCanvas().style.cursor = ''; } };
  }, [sentinel.active, sentinel.tool, sentinel.click, camera]);

  useEffect(() => {
    if (!sentinel.active) return;
    const source = 'sentinel-selection';
    const layers = ['sentinel-aoi-fill', 'sentinel-aoi-outline', 'sentinel-point'];
    const markers = sentinelMarkers(sentinel.bounds, sentinel.corner, sentinel.position);
    const remove = [leftMap.current, rightMap.current].flatMap(map => {
      if (!map) return [];
      const cancel = afterAdminStyle(map, () => {
        map.addSource(source, { type: 'geojson', data: markers });
        map.addLayer({ id: layers[0], type: 'fill', source, filter: ['==', '$type', 'Polygon'],
          paint: { 'fill-color': '#18d8ff', 'fill-opacity': 0.12 } });
        map.addLayer({ id: layers[1], type: 'line', source, filter: ['==', '$type', 'Polygon'],
          paint: { 'line-color': '#18d8ff', 'line-width': 3 } });
        map.addLayer({ id: layers[2], type: 'circle', source, filter: ['==', '$type', 'Point'],
          paint: { 'circle-color': '#fcbd38', 'circle-radius': 6, 'circle-stroke-color': '#152344', 'circle-stroke-width': 2 } });
      });
      return [() => { cancel(); if (!map.getStyle()) return;
        layers.forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
        if (map.getSource(source)) map.removeSource(source); }];
    });
    return () => remove.forEach(cleanup => cleanup());
  }, [sentinel.active, sentinel.bounds, sentinel.corner, sentinel.position, camera]);

  useEffect(() => {
    if (isDisaster) return;
    let active = true;
    setBoundaryError(false);
    void allAdminBoundaries().then(data => {
      if (active) setHeldBoundary(data);
    }).catch(() => { if (active) setBoundaryError(true); });
    return () => { active = false; };
  }, [isDisaster]);

  useEffect(() => {
    if (isDisaster || !boundary) return;
    const removeHandlers: (() => void)[] = [];
    for (const map of [leftMap.current, rightMap.current]) {
      if (!map) continue;
      const selectDistrict = (event: maplibregl.MapLayerMouseEvent) => {
        const name = event.features?.[0]?.properties?.name;
        if (typeof name === 'string') setBoundaryName(name);
      };
      const removeWait = afterAdminStyle(map, () => {
        drawAdminBoundaries(map, boundary, showBoundary);
        if (showBoundary) map.on('click', adminBoundaryStartLayer, selectDistrict);
      });
      removeHandlers.push(() => {
        removeWait();
        if (showBoundary) map.off('click', adminBoundaryStartLayer, selectDistrict);
      });
    }
    return () => removeHandlers.forEach(remove => remove());
  }, [camera, boundary, showBoundary, isDisaster]);

  function setView(value: typeof mode) {
    setMode(value); setPlay(false); setSwipePlayback(undefined); setLaterFrame(false);
    setArchiveFrame(undefined);
  }
  function stepYear(direction: number) {
    setPlay(false);
    if (!enhancedLandsat) {
      setLaterFrame(value => !value);
      return;
    }
    const index = archiveYears.indexOf(visibleArchiveYear) + direction;
    setArchiveFrame(archiveYears[index] ?? visibleArchiveYear);
  }
  function toggleSwipePlayback() {
    const now = performance.now();
    if (swipePlayback?.state === 'playing') {
      const elapsed = now - swipePlayback.startedAt;
      if (elapsed >= SWIPE_AUTO_PLAY_MS) {
        setPosition(50);
        setSwipePlayback({ state: 'finished' });
      } else {
        setSwipeSeconds(Math.ceil((SWIPE_AUTO_PLAY_MS - elapsed) / 1000));
        setSwipePlayback({ state: 'paused', elapsed });
      }
      return;
    }
    const elapsed = swipePlayback?.state === 'paused' ? swipePlayback.elapsed : 0;
    if (!elapsed) setPosition(50);
    setSwipeSeconds(Math.ceil((SWIPE_AUTO_PLAY_MS - elapsed) / 1000));
    setSwipePlayback({ state: 'playing', startedAt: now - elapsed });
  }
  function fit(target: Bounds) {
    leftMap.current?.fitBounds([[target[0], target[1]], [target[2], target[3]]], { padding: 26 });
  }
  const rasterFallback = isDisaster || mapFallback;
  const showRight = mode === 'swipe';
  const playLabel = archivePlaying ? String(visibleArchiveYear) : labels[laterFrame ? 1 : 0];
  return <><div className="mw-swipe-wrapper" data-testid="lcluc-existing-map" ref={containerRef}>
    <div className="mw-swipe-canvas" ref={leftRef}>
      {rasterFallback && shownOnLeft && <img className="mw-native-imagery" src={shownOnLeft} alt={mode === 'animate' ? playLabel : labels[0]} style={{ opacity }}/>}
      {rasterFallback && [leftCover, leftQuality, leftChange].map((url, index) => url && <img key={url}
        className="mw-native-imagery" src={url} alt="" style={{ opacity: [0.48, 0.85, 0.86][index] * opacity }}/>)}
    </div>
    <div className="mw-swipe-canvas mw-swipe-right" ref={rightRef} style={{ clipPath: `inset(0 0 0 ${showRight ? position : 100}%)`, background: rasterFallback ? '#0d3a55' : undefined }}>
      {rasterFallback && rightSource && <img className="mw-native-imagery" src={rightSource} alt={labels[1]} style={{ opacity }}/>}
      {rasterFallback && [rightCover, rightQuality, changeOverlay].map((url, index) => url && <img key={url}
        className="mw-native-imagery" src={url} alt="" style={{ opacity: [0.48, 0.85, 0.86][index] * opacity }}/>)}
    </div>
    <span className="mw-swipe-badge mw-swipe-badge-left">{mode === 'animate' ? `📅 Play: ${playLabel}` : `◀ T1 Baseline: ${labels[0]}`}</span>
    {showRight && <span className="mw-swipe-badge mw-swipe-badge-right">T2 Comparison: {labels[1]} ▶</span>}
    <div className="mw-collection-status-badge" style={{ position: 'absolute', bottom: 70, left: 10, zIndex: 8 }}>
      <span>{source?.attribution ?? (provinceMode ? `${opticalSensor ? opticalTitles[opticalSensor] : 'Esri / Impact Observatory v003'} · ${landsat.active ? '반텐주 유효 관측' : '반텐주 전역'}` : detail?.taxonomy_id === 'esri-io-v003' ? 'Esri / Impact Observatory v003 · 연차 참조' : '연차 토지피복')}{!isDisaster && (landsat.active ? ' · 짙은 남색 관측 공백' : ' · 배경 Tiles © Esri')}</span>
    </div>
    {!hasData && <div className={`mw-nodata-overlay${showBoundary && boundary && !rasterFallback ? ' mw-boundary-backed' : ''}`}><span>{layerStatus}</span></div>}
    {showRight && <div className="mw-swipe-divider" style={{ left: `${position}%` }}>
      <button type="button" className="mw-swipe-handle" aria-label="Swipe 분할선 드래그"
        onPointerDown={event => { setSwipePlayback(undefined); event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={event => {
          if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
          const box = containerRef.current?.getBoundingClientRect();
          if (box?.width) setPosition(Math.min(99, Math.max(1, Math.round((event.clientX - box.left) * 100 / box.width))));
        }}
        onKeyDown={event => {
          if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
          event.preventDefault();
          setSwipePlayback(undefined);
          setPosition(value => Math.max(0, Math.min(100, value + (event.key === 'ArrowRight' ? 1 : -1))));
        }}>‹ ›</button>
    </div>}
    <div className="mw-swipe-toolbar" role="toolbar" aria-label="Time-Series Analysis Controls">
      <button type="button" className={`mw-mode-btn ${showRight ? 'active' : ''}`} onClick={() => setView('swipe')}>⬌ Swipe</button>
      <button type="button" className={`mw-mode-btn ${mode === 'animate' ? 'active' : ''}`} onClick={() => setView('animate')}>🎞️ Time-Series</button>
      <button type="button" className={`mw-mode-btn ${mode === 'single' ? 'active' : ''}`} onClick={() => setView('single')}>Single View</button>
      {showRight && <>
        <div className="mw-swipe-playback">
          <button type="button" className="mw-swipe-btn" disabled={!hasData}
            title="5초 동안 한 번 재생한 뒤 50:50으로 돌아갑니다"
            onClick={toggleSwipePlayback}>
            {swipePlayback?.state === 'playing' ? '⏸ Pause' : swipePlayback?.state === 'paused' ? '▶ Resume' : '▶ Auto Play'}
          </button>
          {hasData && swipePlayback && <span className="mw-swipe-playback-status" role="status">
            {swipePlayback.state === 'finished' ? '재생 완료' : `${swipePlayback.state === 'paused' ? '일시 정지 · ' : ''}${swipeSeconds}초 남음`}
          </span>}
        </div>
        {isDisaster ? <button type="button" className="mw-swipe-btn"
          onClick={() => { setSwipePlayback(undefined); setPosition(100); }}>◀ {labels[0]}</button>
          : <label className="mw-swipe-year"><span>T1</span>
            <select aria-label="지도 기준 연도" value={startYear} onChange={event => onYearChange('start', event.target.value)}>
              {yearOptions.map(year => <option key={year} disabled={Number(year) >= endYear}>{year}</option>)}
            </select>
          </label>}
        <button type="button" className="mw-swipe-btn"
          onClick={() => { setSwipePlayback(undefined); setPosition(50); }}>50:50</button>
        {isDisaster ? <button type="button" className="mw-swipe-btn"
          onClick={() => { setSwipePlayback(undefined); setPosition(0); }}>{labels[1]} ▶</button>
          : <label className="mw-swipe-year"><span>T2</span>
            <select aria-label="지도 비교 연도" value={endYear} onChange={event => onYearChange('end', event.target.value)}>
              {yearOptions.map(year => <option key={year} disabled={Number(year) <= startYear}>{year}</option>)}
            </select>
          </label>}
        <label>Split: <input type="range" aria-label="Time-Series Swipe Slider" min="0" max="100" value={position} onChange={event => { setSwipePlayback(undefined); setPosition(Number(event.target.value)); }}/><b>{position}%</b></label>
      </>}
      {mode === 'animate' && <>
        <button type="button" className="mw-swipe-btn" disabled={!hasData} onClick={() => {
          if (!play && archivePlaying && visibleArchiveYear === endYear) setArchiveFrame(startYear);
          setPlay(!play);
        }}>{play ? '⏸ Pause' : '▶ Play'}</button>
        <button type="button" className="mw-swipe-btn" aria-label="Previous Year" onClick={() => stepYear(-1)}>◀</button>
        <span aria-label="재생 연도">{playLabel}</span>
        {archivePlaying && <span aria-label="재생 진행">{archiveYears.indexOf(visibleArchiveYear) + 1}/{archiveYears.length}</span>}
        <button type="button" className="mw-swipe-btn" aria-label="Next Year" onClick={() => stepYear(1)}>▶</button>
        <select aria-label="Playback Speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          <option value={2000}>0.5x</option><option value={1500}>1.0x</option><option value={800}>2.0x</option>
        </select>
      </>}
      <button type="button" className="mw-mode-btn" disabled={rasterFallback} onClick={() => {
        setProvinceSelected(false); onProvinceView(false); setClassFilter(undefined);
        fit(sample ?? bounds);
      }}>🎯 10m Study AOI</button>
      <button type="button" className="mw-mode-btn" disabled={rasterFallback || !reg} onClick={() => {
        if (reg) fit(reg.provinceBbox);
        setProvinceSelected(true); onProvinceView(true); setClassFilter(undefined);
      }}>🗺️ Province AOI</button>
      <button type="button" className="mw-mode-btn" disabled={rasterFallback || !boundary}
        onClick={() => { setShowBoundary(true); setBoundaryName(''); fit([104, -10, 126, 2]); }}>6개 주 전체</button>
      <button type="button" className={`mw-mode-btn ${showBoundary ? 'active' : ''}`} disabled={rasterFallback || !boundary} aria-pressed={showBoundary && Boolean(boundary)} onClick={() => { setShowBoundary(value => !value); setBoundaryName(''); }}>🌐 Boundary {showBoundary ? 'ON' : 'OFF'}</button>
      <button type="button" className={`mw-mode-btn ${(sentinel.active ? sentinel.quality : showQualityMask) && !isDisaster ? 'active' : ''}`}
        disabled={isDisaster || opticalSensor === 'landsat' || (sentinel.active ? !enhancedSentinel : !hasData)}
        title={cloudColor ? 'Esri 구름 픽셀을 표시' : '구름·그림자·관측 공백을 표시'}
        onClick={() => sentinel.active ? sentinel.setQuality(!sentinel.quality) : setShowQualityMask(value => !value)}>
        ☁️ Quality Mask{(sentinel.active ? sentinel.quality : showQualityMask) && !isDisaster ? ' ON' : ''}
      </button>
    </div>
    <div className="mw-map-tools" role="group" aria-label="지도 조작">
      <button type="button" aria-label="지도 확대" disabled={rasterFallback} onClick={() => leftMap.current?.zoomIn()}><Icon name="plus" size={19}/></button>
      <button type="button" aria-label="지도 축소" disabled={rasterFallback} onClick={() => leftMap.current?.zoomOut()}><Icon name="minus" size={19}/></button>
      <button type="button" aria-label="연구지역 전체 맞춤" disabled={rasterFallback} onClick={() => fit(camera)}><Icon name="home" size={19}/></button>
    </div>
    <div className={`mw-map-legend mw-lcluc-legend${sentinel.active || landsat.active ? ' mw-sentinel-map-legend' : ''}`} aria-label="Land Cover Legend">
      <strong>{opticalSensor ? opticalTitles[opticalSensor] : source?.title ?? 'Land Cover'}</strong>
      {(options.length > 0 || fullBanten) && <select aria-label="지도 자료" value={opticalSensor ?? source?.id ?? 'land-cover'} onChange={event => {
        setLayer(event.target.value); setClassFilter(undefined); setShowQualityMask(false); setPosition(50); setPlay(false); setSwipePlayback(undefined); setLaterFrame(false);
      }}>
        <option value="land-cover">연차 토지피복도</option>
        {fullBanten && <>
          <option value="sentinel-2">Sentinel-2 L2A · 반텐 전역</option>
          <option value="landsat">Landsat C2 L2 · 반텐 전역</option>
        </>}
        {options.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select>}
      {sentinel.active && <SentinelLayerControls explorer={sentinel} start={startYear} end={endYear}
        showBoundary={showBoundary} toggleBoundary={() => { setShowBoundary(!showBoundary); setBoundaryName(''); }}
        mapInteractive={!rasterFallback}/>}
      {landsat.active && <LandsatLayerControls explorer={landsat} end={endYear} pairReady={enhancedLandsat}/>}
      {sentinel.active && sentinel.cover && <div className="mw-lcluc-legend-list" role="list" aria-label="Esri 토지피복 클래스 범례">
        {Object.entries(provinceData?.colors ?? {}).filter(([code]) => Number(code) in ESRI_CLASS_NAMES)
          .map(([code, color]) => <div key={code} role="listitem" className="mw-lcluc-legend-row">
            <i style={{ backgroundColor: color }}/><span>{ESRI_CLASS_NAMES[Number(code)]}</span>
          </div>)}
      </div>}
      {sentinel.active && sentinel.change && sentinel.canChange && <small>
        <i className="mw-sentinel-swatch" style={{ background: '#f22080' }}/>
        {sentinel.transition ? <>
          {ESRI_CLASS_NAMES[sentinel.transition.from]} → {ESRI_CLASS_NAMES[sentinel.transition.to]}
          <button type="button" className="mw-sentinel-clear-filter" onClick={sentinel.clearTransition}>전체 전이 표시</button>
        </> : 'Esri 분류 변화 · 비교 화면'}
      </small>}
      {sentinel.active && sentinel.quality && enhancedSentinel && <small>연한 노랑 구름 · 보라 그림자 · 회색 관측 공백</small>}
      {!source && legendRows.length > 0 && <>
        <div className="mw-lcluc-legend-list" role="group" aria-label="분류 필터">{legendRows.map(item => {
          const isCloud = Boolean(cloudColor && item.code === 10);
          return <label className="mw-lcluc-legend-row" key={item.code} title={isCloud ? '구름 픽셀 표시 · 변화 통계 제외' : undefined}>
            <input type="checkbox" checked={isCloud ? showQualityMask : classFilter?.includes(item.color) ?? true} onChange={event => {
              const checked = event.target.checked;
              if (isCloud) {
                setShowQualityMask(checked);
                return;
              }
              const current = classFilter ?? legendClasses.map(entry => entry.color);
              setClassFilter(checked ? [...current, item.color] : current.filter(color => color !== item.color));
            }}/>
            <i style={{ background: item.color }}/><span>{item.name}</span>
          </label>;
        })}</div>
      </>}
      {source && <><small>{source.scope}</small><a href={source.earlier.bundle}>T1 ZIP</a><a href={source.later.bundle}>T2 ZIP</a></>}
      {!sentinel.active && !landsat.active && (source || detail || provinceMode) && <details className="mw-lcluc-layer-details">
        <summary>자료 및 사용처</summary>
        {opticalSensor ? <>
          <p>{imageryUse[opticalSensor].files} · 반텐 경계 · QA 적용</p>
          {[startYear, endYear].map(year => <p key={year}>{year}년 {opticalYears?.[year] ?
            `${opticalYears[year].scene_count}개 원본 장면 · 표시 격자 유효 ${ha.format(opticalYears[year].display_clear_pct)}%` : '원본 장면 검증 중'}</p>)}
        </> : source ? <>
          <p>{source.attribution} · {imageryUse[source.id].files}</p>
          <p>{imageryUse[source.id].purpose} · {source.earlier.observed_on} / {source.later.observed_on}</p>
          {source.id !== 'disaster' && <p>T1 {source.earlier.scene}<br/>T2 {source.later.scene}</p>}
        </> : <p>{provinceMode ? '반텐주 전체 · Esri / Impact Observatory v003' : esri ? 'Esri / Impact Observatory v003 · 10m 분류 GeoTIFF' : '등록 연차 분류 GeoTIFF'} · {startYear} / {endYear} · {provinceMode ? '연차 색상 비교 · 시범 지표는 시험 구역 기준' : '변화 면적과 전환행렬 계산'}</p>}
      </details>}
      {!sentinel.active && !landsat.active && !rasterFallback && boundary && showBoundary && <div className="mw-admin-boundary-legend" aria-label="행정경계 범례">
        <span><i className="mw-admin-province-key"/>주 경계{provinceName && ` · ${provinceName}`}</span>
        <span><i className="mw-admin-district-key"/>군·시 경계</span>
        {boundaryName && <strong role="status">{boundaryName}</strong>}
        <small><a href={boundary.source.uri} target="_blank" rel="noreferrer">{boundary.source.label}</a> · {boundary.source.acquired_at.slice(0, 10)} 취득</small>
        {!boundary.source.approved_for_project_statistics && <small>사업 통계 승인 대기</small>}
      </div>}
      {(sentinel.active || landsat.active) && showBoundary && boundaryName && <strong role="status">{boundaryName}</strong>}
      {!rasterFallback && boundaryError && <small role="status">One Map 경계 자료를 확인할 수 없습니다.</small>}
      <label className="mw-lcluc-legend-opacity">Opacity <input aria-label="Adjust Land Cover Layer Opacity" type="range" min={0} max={1} step={0.05} value={opacity} onChange={event => setOpacity(Number(event.target.value))}/></label>
    </div>
  </div>{sentinel.active && <SentinelAnalysisPanel explorer={sentinel} start={startYear} end={endYear}
    names={ESRI_CLASS_NAMES} mapInteractive={!rasterFallback}
    downloadsId={downloadsId} onShowMap={onShowMap}/>}</>;
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
  const maxVal = Math.max(1, ...points.flatMap(point => point.values));
  const step = 10 ** Math.floor(Math.log10(maxVal));
  const axisMax = Math.ceil(maxVal / step) * step;
  const height = 115;
  const left = 48;
  const right = 286;
  const top = 15;
  const bottom = top + height;
  const ticks = [0, axisMax / 2, axisMax];
  const getY = (val: number) => bottom - (val / axisMax) * height;
  const getX = (idx: number) => left + (idx / Math.max(1, years.length - 1)) * (right - left);

  return (
    <div className="mw-chart mw-chart-time">
      <span className="mw-chart-unit">{unit}</span>
      <svg viewBox="0 0 300 155" role="img" aria-label="연차별 면적 변화 추이">
        <g stroke="#e1eaf6" strokeWidth="1">
          {ticks.map(value => (
            <path key={value} d={`M${left} ${getY(value)}H${right}`} />
          ))}
          {years.map((_, i) => (
            <path key={i} d={`M${getX(i)} ${top}V${bottom}`} />
          ))}
        </g>
        <path d={`M${left} ${top}V${bottom}H${right}`} fill="none" stroke="#8ba5cd" />
        <g fill="#6885b7" fontSize="9">
          {ticks.map(value => (
            <text key={value} x={left - 5} y={getY(value)} dy=".32em" textAnchor="end">{ha.format(value)}</text>
          ))}
          {years.map((v, i) => (
            <text key={v} x={getX(i)} y="146" textAnchor="middle">{v}</text>
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
                >
                  <title>{`${years[i]} · ${series.label} · ${ha.format(v)} ${unit}`}</title>
                </circle>
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
  id,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
  icon?: string;
  id?: string;
}) {
  return (
    <section className="mw-card" id={id} tabIndex={id ? -1 : undefined} aria-labelledby={id ? id + '-title' : undefined}>
      <div className="mw-card-title">
        <h3 id={id ? id + '-title' : undefined}>
          <Icon name={icon || panelIcon(title)} size={19} />
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

type SentinelDestination = 'map' | 'observations' | SentinelResultId;
const sentinelNavigation: [SentinelDestination, string][] = [
  ['map', '지도 분석'],
  ...(Object.entries(sentinelResultTitles) as [SentinelResultId, string][]),
];
const landsatNavigation: [SentinelDestination, string][] = [
  ['map', '지도 분석'], ['observations', '영상·관측 품질'], ['change', '장기 변화탐지'],
  ['trend', '시계열 통계'], ['classification', 'AI 모델 비교'],
];

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
  const [sentinelDestination, setSentinelDestination] = useState<SentinelDestination>('map');
  const sentinelId = useId();
  const [mapSource, setMapSource] = useState<{ region: string; layer: string }>();
  const [notice, setNotice] = useState('');
  const [guide, setGuide] = useState(false);
  const [refreshPair, setRefreshPair] = useState(0);
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
  const bantenAoi = agentId === 'lcluc' && regEntry?.id === 'banten';
  const aoiSelection = bantenAoi ? draft.bantenAoi || '주 전체 참조'
    : draft['세부 지역 (AOI)'] || '연구 bbox';
  const bounds = (agentId === 'lcluc' && regEntry)
    ? (aoiSelection === '주 전체 참조' ? regEntry.provinceBbox : regEntry.researchBbox)
    : (selectableRegions.find(([name]) => name === region)?.[1] || selectableRegions[0][1]);

  const startYear = Number(draft['시작 연도'] || '2020');
  const endYear = Number(draft['종료 연도'] || '2025');

  const isLcluc = agentId === 'lcluc';
  const provinceScope = isLcluc && regEntry?.id === 'banten' && aoiSelection === '주 전체 참조';
  const mapLayer = mapSource?.region === region ? mapSource.layer : 'land-cover';
  const sentinel = useSentinelExplorer(provinceScope && mapLayer === 'sentinel-2' && active === 0, startYear, endYear);
  const landsat = useLandsatExplorer(provinceScope && mapLayer === 'landsat' && active === 0);
  const opticalWorkspace = sentinel.active || landsat.active;
  const publishedYears = landsat.active ? landsat.catalog?.annual.map(item => item.key) ?? [] : [];
  const mapYears = publishedYears.length >= 2 ? publishedYears : years;
  const preferredStart = landsat.active ? draft.landsatStart || String(startYear) : String(startYear);
  const preferredEnd = landsat.active ? draft.landsatEnd || String(endYear) : String(endYear);
  const usePair = mapYears.includes(preferredStart) && mapYears.includes(preferredEnd) && preferredStart < preferredEnd;
  const mapStart = Number(landsat.active && !usePair ? mapYears[0] : preferredStart);
  const mapEnd = Number(landsat.active && !usePair ? mapYears.at(-1) : preferredEnd);
  function sentinelSectionId(section: SentinelDestination | 'downloads') {
    return `${sentinelId}-sentinel-${section}`;
  }
  function goToSentinel(section: SentinelDestination | 'downloads') {
    const target = document.getElementById(sentinelSectionId(section));
    if (!target) return;
    if (section !== 'downloads') setSentinelDestination(section);
    if (target instanceof HTMLDetailsElement) target.open = true;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'start' });
  }
  function setMapLayer(layer: string) {
    setMapSource({ region, layer });
    if (layer === 'sentinel-2' || layer === 'landsat') setSentinelDestination('map');
    if (layer !== 'sentinel-2') sentinel.cancelTool();
  }
  const province = useBantenComparison(provinceScope, startYear, endYear);
  const { detail, imagery, status } = useLclucExplorer(isLcluc, regEntry?.id ?? '', startYear, endYear, refreshPair);
  const report = provinceScope ? undefined : detail?.report;
  const bantenResult = province.comparison;
  const annualAreas = bantenResult?.annual_area ?? [];
  const area = bantenResult?.common_valid_area_ha ?? report?.coverage.common_valid_area_ha;
  const yearsShown = provinceScope ? annualAreas.map(row => row.year) : [startYear, endYear];
  const provinceColors = ['#419bdf','#397d49','#7a87c6','#e49635','#c4281b','#a59b8f','#a8ebff','#e3e2c3'];
  const points = provinceScope ? bantenResult?.classes.map((item, index) => ({
    label: item.name, color: provinceColors[index], values: annualAreas.map(row => row.areas_ha[item.code]),
  })) ?? [] : report?.annual_stats.map((item, index) => ({
    label: report.classes[index].name,
    color: detail?.esri_display?.colors[item.code] ?? report.classes[index].color,
    values: [item.from_area_ha, item.to_area_ha],
  })) ?? [];
  const flowClasses = bantenResult?.classes ?? report?.classes ?? [];
  const flowMatrix = bantenResult?.transition_matrix_ha ?? report?.transition_matrix_ha ?? [];
  const changedArea = bantenResult?.changed_area_ha ?? report?.major_changes.changed_area_ha ?? 0;
  const flows = flowMatrix.flatMap((row, i) => row.flatMap((amount, j) =>
    i !== j && amount > 0 ? [{ source: flowClasses[i].name, target: flowClasses[j].name, amount }] : [],
  )).sort((a, b) => b.amount - a.amount).slice(0, 5);
  const chosenMetric = draft.chartMetric || points[0]?.label;
  const showSnowEvidence = provinceScope && bantenResult?.classes.some(
    item => item.code === 9 && item.name === chosenMetric,
  );
  const chartPoints = chosenMetric === 'Total Valid Area' && points.length ? [{
    label: '유효 토지피복 총면적', color: '#146059',
    values: yearsShown.map((_, i) => points.reduce((sum, point) => sum + point.values[i], 0)),
  }] : points.some(point => point.label === chosenMetric) ? points.filter(point => point.label === chosenMetric) : points;
  const sourceName = detail?.taxonomy_id === 'esri-io-v003' ? 'Esri / Impact Observatory v003' : '연차 토지피복';
  const annualLandCoverContext = provinceScope
    ? `Esri / Impact Observatory v003 · 반텐주 전체 · ${startYear}→${endYear}`
    : report ? `${sourceName} · 고정 시험 구역 · ${startYear}→${endYear}` : '연차 토지피복 결과 미등록';
  const assetLabels: Record<string, string> = {
    report: '검증 보고서 JSON', matrix: '전환행렬 CSV', hotspots: '핫스팟 GeoJSON',
    transition: '변화 GeoTIFF', earlier: '기준 연도 TIFF', later: '비교 연도 TIFF',
  };

  function matrix() {
    if (!report) return <p className="mw-disconnected">{status}</p>;
    return <div className="mw-table-scroll" style={{ maxHeight: 315 }}><table className="mw-table mw-matrix-table">
      <caption>토지피복 전이 면적 (ha)</caption>
      <thead><tr><th>T1 → T2</th>{report.classes.map(item => <th key={item.code}>{item.name}</th>)}</tr></thead>
      <tbody>{report.transition_matrix_ha.map((row, i) => <tr key={report.classes[i].code}>
        <th>{report.classes[i].name}</th>{row.map((amount, j) => <td key={report.classes[j].code} className={i === j ? 'highlight-diag' : amount > 0 ? 'highlight-change' : undefined}>{ha.format(amount)}</td>)}
      </tr>)}</tbody>
    </table></div>;
  }

  function provinceMatrix() {
    const data = bantenResult;
    if (!data) return <p className="mw-disconnected" role="status">{province.status}</p>;
    return <div className="mw-table-scroll">
      <table className="mw-table mw-matrix-table">
        <caption>{data.from_year}–{data.to_year} 반텐주 전체 토지피복 전이 면적 (ha)</caption>
        <thead><tr><th>T1 → T2</th>{data.classes.map(item => <th key={item.code}>{item.name}</th>)}</tr></thead>
        <tbody>{data.transition_matrix_ha.map((row, i) => <tr key={data.classes[i].code}>
          <th>{data.classes[i].name}</th>
          {row.map((amount, j) => <td key={data.classes[j].code} className={i === j ? 'highlight-diag' : undefined}>{ha.format(amount)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>;
  }

  function provincePanel() {
    const data = province.comparison;
    if (active === 6) return <div className="mw-dataset-status">
      <p role="status">{province.status}</p>
      {province.report && <>
        <a href={province.report.assets.html} target="_blank" rel="noreferrer">반텐주 전역 보고서 열기</a>
        <a href={province.report.assets.json} download>보고서 JSON</a>
        <a href={province.report.assets.csv} download>전환행렬 CSV</a>
      </>}
    </div>;
    if (!data) return <p className="mw-disconnected" role="status">{province.status}</p>;
    if (active === 1) return <div className="mw-large-chart">
      <LclucRealChart years={yearsShown} points={points} unit="ha"/>
      <div className="mw-table-scroll"><table className="mw-table">
        <caption>반텐주 연도별 유효 토지피복 면적 (ha)</caption>
        <thead><tr><th>연도</th>{data.classes.map(item => <th key={item.code}>{item.name}</th>)}<th>유효율</th></tr></thead>
        <tbody>{annualAreas.map(row => <tr key={row.year}><th scope="row">{row.year}</th>
          {data.classes.map(item => <td key={item.code}>{ha.format(row.areas_ha[item.code])}</td>)}
          <td>{ha.format(row.thematic_valid_pct)}%</td>
        </tr>)}</tbody>
      </table></div>
    </div>;
    if (active === 2 || active === 4) {
      if (!data.spatial) return <p className="mw-disconnected">분석 실행으로 이 연도쌍의 반텐주 전역 변화지도를 계산하세요.</p>;
      const { spatial } = data;
      return <div>
        <div className="mw-control-bar"><span>1km 격자 변화율</span>
          <small>{ha.format(spatial.changed_grid_cells)}개 변화 격자 · 10m 공통 유효 픽셀 집계</small>
        </div>
        <LclucChangePreviewMap bounds={spatial.bounds} url={spatial.preview} hotspots={active === 4 ? spatial.hotspots : undefined}/>
        {active === 4 ? <div className="mw-table-scroll"><table className="mw-table">
          <caption>반텐주 전역 변화 면적 상위 20개 격자</caption>
          <thead><tr><th>순위</th><th>변화 (ha)</th><th>공통 유효 (ha)</th><th>변화율</th></tr></thead>
          <tbody>{spatial.hotspots.map(row => <tr key={row.rank}><th scope="row">{row.rank}</th>
            <td>{ha.format(row.changed_area_ha)}</td><td>{ha.format(row.common_valid_area_ha)}</td><td>{ha.format(row.rate_pct)}%</td>
          </tr>)}</tbody>
        </table></div> : <p className="mw-disconnected">회색 1% 미만 · 옅은 주황 1–10% · 주황 10–25% · 진한 주황 25–50% · 적색 50% 이상</p>}
      </div>;
    }
    return <div>
      <p role="status">{province.status}</p>
      <p>반텐주 전체 {ha.format(data.boundary_area_ha)} ha · 공통 유효 {ha.format(data.common_valid_area_ha)} ha · 변화 {ha.format(data.changed_area_ha)} ha</p>
      {provinceMatrix()}
    </div>;
  }

  function downloads() {
    if (!detail) return <p className="mw-disconnected">{status}</p>;
    return <div className="mw-dataset-status"><a href={resultReviewHash(detail.id)}>공통 결과 상세·검토</a>
      {detail.assets.map(asset => <a key={asset.id} href={asset.href}>{assetLabels[asset.id] || asset.id}</a>)}
    </div>;
  }

  function opticalCoverage(sensor: 'sentinel-2' | 'landsat') {
    return province.collection?.optical_qa?.[sensor]?.map(row => {
      const clear = row.sentinel_clear_pct ?? row.landsat_clear_pct;
      return <ReactFragment key={row.year}>
        <br/>{row.year}년 6밴드 피복 {ha.format(row.six_band_present_pct)}%
        {clear === undefined ? '' : ` · 맑은 픽셀 ${ha.format(clear)}%`}
      </ReactFragment>;
    });
  }

  function update(field: string, value: string) {
    const key = bantenAoi && field === '세부 지역 (AOI)' ? 'bantenAoi' : field;
    const next = { ...drafts, [agentId]: { ...draft, [key]: value } };
    setDrafts(next);
    sessionStorage.setItem('sdss_dense_workspace_drafts', JSON.stringify(next));
  }
  function updateMapYear(side: 'start' | 'end', value: string) {
    if (landsat.active) {
      // Persist both effective ends when one of them came from the published catalogue fallback.
      const next = { ...drafts, [agentId]: { ...draft,
        landsatStart: side === 'start' ? value : String(mapStart),
        landsatEnd: side === 'end' ? value : String(mapEnd),
      } };
      setDrafts(next);
      sessionStorage.setItem('sdss_dense_workspace_drafts', JSON.stringify(next));
    } else update(side === 'start' ? '시작 연도' : '종료 연도', value);
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

  const esri = detail?.taxonomy_id === 'esri-io-v003';
  const thematic = (code: number) => report?.annual_stats.find(item => item.code === code);
  const provinceStart = annualAreas.find(row => row.year === startYear);
  const provinceEnd = annualAreas.find(row => row.year === endYear);
  const kpi = provinceStart && provinceEnd ? [2, 7, 5].map(code => ({
    to_area_ha: provinceEnd.areas_ha[code],
    net_ha: provinceEnd.areas_ha[code] - provinceStart.areas_ha[code],
  })) : esri ? [thematic(2), thematic(7), thematic(5)] : [];
  const kpiValues = [0, 1, 2].map(i => kpi[i] ? ha.format(kpi[i].to_area_ha) : '—')
    .concat(area === undefined ? '—' : ha.format(area));
  const kpiDeltas = [0, 1, 2].map(i => kpi[i] ? `${ha.format(kpi[i].net_ha)} ha 순변화` : '—')
    .concat(bantenResult?.change_rate_pct != null ? `전이율 ${ha.format(bantenResult.change_rate_pct)}%`
      : report ? `전이율 ${ha.format(report.major_changes.change_rate_pct)}%` : '—');
  const kpiSubtexts = provinceScope ? [
    '반텐주 전체 · 비교 연도 유효 픽셀', '반텐주 전체 · 비교 연도 유효 픽셀',
    '반텐주 전체 · 비교 연도 유효 픽셀', '반텐주 전체 · 공통 유효 픽셀',
  ] : Array<string>(4).fill(report ? '고정 시험 구역 · 공통 유효 픽셀' : '검증 결과 미연결');

  function sentinelCard(result: SentinelResultId) {
    return <Card id={sentinelSectionId(result)} title={sentinelResultTitles[result]} icon={result === 'area' ? 'donut' : undefined}>
      <SentinelResult result={result} explorer={sentinel} start={startYear} end={endYear}
        colors={Object.fromEntries(Object.keys(ESRI_CLASS_NAMES).map((code, index) => [code, provinceColors[index]]))}
        onShowMap={() => goToSentinel('map')}/>
    </Card>;
  }

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
        {isLcluc && <button type="button" className="mw-small-button" onClick={() => onNavigate(LCLUC_POSTPROCESS_STEP)}>
          후처리 및 품질관리
        </button>}
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
              aria-label={label}
              value={label === '세부 지역 (AOI)' ? aoiSelection
                : label === '시작 연도' && landsat.active ? mapStart
                : label === '종료 연도' && landsat.active ? mapEnd
                : draft[label] || options[label.includes('종료') || label.includes('비교') ? options.length - 1 : 0]}
              onChange={e => {
                if (label === '시작 연도' || label === '종료 연도') updateMapYear(label === '시작 연도' ? 'start' : 'end', e.target.value);
                else update(label, e.target.value);
              }}
            >
              {(landsat.active && (label === '시작 연도' || label === '종료 연도') ? mapYears : options).map(option => (
                <option key={option} disabled={isLcluc && (
                  (label === '시작 연도' && Number(option) >= mapEnd) ||
                  (label === '종료 연도' && Number(option) <= mapStart)
                )}>{option}</option>
              ))}
            </select>
          </label>
        ))}
        <div className="mw-run-actions">
          <button
            className="mw-run"
            onClick={() => {
              if (sentinel.active) {
                sentinel.refreshStatistics();
                goToSentinel('area');
              } else if (landsat.active) {
                goToSentinel('observations');
              } else if (provinceScope) {
                choose(3);
                province.perform('analysis');
              } else if (agentId === 'lcluc') {
                setRefreshPair(value => value + 1);
                setNotice(`${region} ${startYear}–${endYear} 등록 결과를 다시 조회합니다.`);
              } else {
                onTab('evidence');
                setNotice('실행 전 준비도·승인 gate를 확인하세요. 아래 검증·근거에서 실제 계약을 검토할 수 있습니다.');
              }
            }}
          >
            <Icon name="play" size={20} />
            <span>{sentinel.active ? 'AOI 통계 갱신' : landsat.active ? '영상·품질 확인' : '분석 실행'}</span>
          </button>
          <button
            className="mw-compare"
            onClick={() => {
              if (sentinel.active) {
                goToSentinel('matrix');
                return;
              }
              if (landsat.active) {
                goToSentinel('change');
                return;
              }
              choose(5);
              if (provinceScope) province.perform('comparison');
              setNotice(provinceScope ? '반텐주 전체 연도 비교를 조회합니다.' : '지역 비교 화면으로 전환되었습니다.');
            }}
          >
            <Icon name="compare" size={20} />
            <span>비교 분석</span>
          </button>
          <button
            className="mw-report"
            onClick={() => {
              if (sentinel.active) {
                goToSentinel('downloads');
                return;
              }
              if (landsat.active) {
                goToSentinel('observations');
                return;
              }
              choose(6);
              if (provinceScope) province.perform('reports');
              else setNotice('결과 내보내기 및 표준 보고서 생성 화면으로 전환되었습니다.');
            }}
          >
            <Icon name="report" size={20} />
            <span>{opticalWorkspace ? '결과 내보내기' : '리포트 생성'}</span>
          </button>
        </div>
      </div>

      {/* 7대 분석 탭 */}
      <nav className="mw-analysis-tabs" aria-label="분야별 분석 기능">
        {opticalWorkspace ? (landsat.active ? landsatNavigation : sentinelNavigation).map(([id, name]) => (
          <button type="button" key={id} className={id === sentinelDestination ? 'active' : ''}
            aria-current={id === sentinelDestination ? 'location' : undefined}
            aria-controls={sentinelSectionId(id)} onClick={() => goToSentinel(id)}>
            <AnalysisIcon label={name}/>{name}
          </button>
        )) : cfg.tabs.map((name, index) => (
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

      {isLcluc && !opticalWorkspace && <div className="mw-stats-invariance-badge" role="status">
        <span className="mw-invariance-pill">{provinceScope ? '반텐주 전체 · Esri / Impact Observatory v003' : report ? sourceName : status}</span>
        {provinceScope && province.comparison && <span className="mw-invariance-desc">공통 유효 {ha.format(province.comparison.common_valid_area_ha)} ha · 변화 {ha.format(province.comparison.changed_area_ha)} ha · 독립 정확도 미측정</span>}
        {report && <span className="mw-invariance-desc">공통 유효 면적 {ha.format(report.coverage.common_valid_area_ha)} ha · 변화 {ha.format(report.major_changes.changed_area_ha)} ha ({ha.format(report.major_changes.change_rate_pct)}%) · 독립 정확도 미측정</span>}
      </div>}

      {/* 상단 메인 그리드 */}
      <div className={opticalWorkspace ? 'mw-primary-grid mw-sentinel-layout' : 'mw-primary-grid'}>
        <Card
          id={opticalWorkspace ? sentinelSectionId('map') : undefined}
          title={mainTitle}
          icon={primaryMode.includes('행렬') ? 'matrix' : chartMode ? 'chart' : 'map'}
          action={
            <button className="mw-small-button" onClick={() => onNavigate(14)}>
              <Icon name="expand" size={14} />
              WebGIS
            </button>
          }
        >
          {isLcluc ? (
            active === 0 ? <LclucSwipeResearchMap key={region} bounds={bounds} region={region} startYear={mapStart} endYear={mapEnd} detail={detail} imagery={imagery} status={status} provinceView={aoiSelection === '주 전체 참조'}
              explorer={sentinel} landsat={landsat} yearOptions={mapYears} layer={mapLayer}
              downloadsId={sentinelSectionId('downloads')} onShowMap={() => goToSentinel('map')}
              onYearChange={updateMapYear}
              setLayer={setMapLayer} onProvinceView={whole => {
              if (regEntry?.id === 'banten') update('세부 지역 (AOI)', whole ? '주 전체 참조' : '연구 bbox');
            }}/>
            : provinceScope ? provincePanel()
            : active === 6 ? downloads()
            : !report || !detail ? <p className="mw-disconnected">{status}</p>
            : active === 1 ? <div className="mw-large-chart">
              <div className="mw-control-bar"><span>{startYear}–{endYear} 분류 면적</span><small>공통 유효 구역</small></div>
              <LclucRealChart years={yearsShown} points={points} unit="ha"/>
              <div className="mw-table-scroll"><table className="mw-table">
                <caption>분류별 공통 유효 면적 비중</caption>
                <thead><tr><th>분류</th><th>{startYear}</th><th>{endYear}</th></tr></thead>
                <tbody>{points.map(point => <tr key={point.label}><th>{point.label}</th>
                  {point.values.map((amount, index) => <td key={yearsShown[index]}>{area ? `${ha.format(100 * amount / area)}%` : '—'}</td>)}
                </tr>)}</tbody>
              </table></div>
            </div>
            : active === 2 || active === 4 ? <div>
              <div className="mw-control-bar"><span>{active === 2 ? '변화 면적' : '연결 픽셀 집중지역'}</span><small>{ha.format(report.major_changes.changed_area_ha)} ha · {report.hotspot_count}개 집중지역</small></div>
              <LclucChangePreviewMap bounds={detail.report.grid.bounds_crs84} url={detail.previews['change-preview']}/>
            </div>
            : active === 3 ? matrix()
            : <div className="mw-table-scroll"><table className="mw-table"><thead><tr><th>구역</th><th>변화 면적</th></tr></thead>
              <tbody>{report.zones.length ? report.zones.map(zone => <tr key={zone.id}><td>{zone.name}</td><td>{ha.format(zone.major_changes.changed_area_ha)} ha</td></tr>)
                : <tr><td>{region} 등록 시험 구역</td><td>{ha.format(report.major_changes.changed_area_ha)} ha</td></tr>}</tbody></table>
              {!report.zones.length && <p className="mw-disconnected">동일 조건의 다른 지역 결과가 등록되면 비교합니다.</p>}
            </div>
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
        {sentinel.active ? <div className="mw-indicator-column mw-sentinel-side">
          {sentinelCard('area')}
          {sentinelCard('classification')}
        </div> : landsat.active ? <div className="mw-indicator-column mw-sentinel-side">
          <Card id={sentinelSectionId('observations')} title="영상·관측 품질">
            <LandsatInventory explorer={landsat} start={mapStart} end={mapEnd}/>
          </Card>
          <Card id={sentinelSectionId('classification')} title="AI 모델 비교"><LclucModelComparison sensor="landsat"/></Card>
        </div> : <div className="mw-indicator-column">
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
            title={`${isLcluc ? '연차 토지피복 ' : ''}주요 지표 (${region})`}
            action={
              <button className="mw-small-button" onClick={() => onTab('evidence')}>
                검증 근거 ›
              </button>
            }
          >
            {isLcluc && <p className="mw-land-cover-source">{annualLandCoverContext}</p>}
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
                        report && i === 0
                          ? '#d92d20'
                          : report && i === 2
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
            title={isLcluc ? '연차 토지피복 주요 전이' : cfg.summary}
            action={
              <button className="mw-small-button" onClick={() => onTab('result')}>
                {isLcluc ? '연차 토지피복 결과 ›' : '상세 결과 ›'}
              </button>
            }
          >
            {isLcluc && <p className="mw-land-cover-source">{annualLandCoverContext}</p>}
            {report || bantenResult ? (
              <div className="mw-table-scroll"><table className="mw-table"><thead><tr>{cfg.columns.map(column => <th key={column}>{column}</th>)}</tr></thead>
                <tbody>{flows.map(flow => <tr key={flow.source + flow.target}><td>{flow.source} → {flow.target}</td><td>{ha.format(flow.amount)} ha</td>
                  <td>{ha.format(changedArea ? 100 * flow.amount / changedArea : 0)}%</td></tr>)}</tbody>
              </table></div>
            ) : (
              <EmptyTable
                columns={cfg.columns}
                rows={cfg.rows}
                rank={agentId !== 'lcluc' && agentId !== 'coastal'}
              />
            )}
          </Card>

          {isLcluc && <Card title="위성영상 수집현황 및 출처" icon="clipboard">
            <div className="mw-collection-status-panel"><table className="mw-table">
              <thead><tr><th>레이어</th><th>실제 자료·시점</th><th>사용처</th></tr></thead>
              <tbody>
                {provinceScope ? <>
                  <tr><th>Esri 연차 토지피복</th><td>{province.collection?.esri_years.length ?? '—'}/6개 연도 검증
                    {province.collection?.esri_years.map(row => <ReactFragment key={row.year}>
                      <br/><a href={row.uri} target="_blank" rel="noreferrer" title={row.sha256}>{row.year} 원본</a> · 유효 {ha.format(row.thematic_valid_pct)}%
                    </ReactFragment>)}</td><td>10m 전역 면적·변화·전환행렬</td></tr>
                  <tr><th>Sentinel-2 L2A</th><td>{province.collection?.sentinel_assets ?? '—'}/224자산 · {province.collection?.sentinel_scenes ?? '—'}/32장면</td>
                    <td>동일 장면 6밴드+SCL 전역 영상{opticalCoverage('sentinel-2')}</td></tr>
                  <tr><th>Landsat 8/9</th><td>{province.collection?.landsat_assets ?? '—'}/168자산 · {province.collection?.landsat_scenes ?? '—'}/24장면</td>
                    <td>6밴드+QA_PIXEL 전역 영상{opticalCoverage('landsat')}</td></tr>
                </> : <>
                  <tr><th>연차 토지피복</th><td>{detail ? `${sourceName} · ${startYear} / ${endYear}` : '비교 자료 미등록'}</td>
                    <td>{detail ? '변화 면적·전환행렬 계산' : '—'}</td></tr>
                {imagery.filter(item => item.region === regEntry?.id || item.id === 'disaster').map(item =>
                  <tr key={item.id}><th>{item.title}</th>
                    <td>{item.earlier.observed_on} / {item.later.observed_on}<br/>{imageryUse[item.id].files}</td>
                    <td>{imageryUse[item.id].purpose}</td></tr>)}
                </>}
                {regEntry && <LclucAnnualIntake region={regEntry.id} />}
              </tbody>
            </table><p>기존 지도 비교의 독립 정확도 미측정</p></div>
            {provinceScope && <details><summary>Esri·MapBiomas 원본별 면적</summary><LclucBantenAreaComparison/></details>}
          </Card>}
        </div>}
      </div>

      {/* 하단 4개 카드 그리드 */}
      {sentinel.active ? <div className="mw-bottom-grid mw-sentinel-results-grid">
        {sentinelCard('matrix')}
        {sentinelCard('change')}
        {sentinelCard('trend')}
        {sentinelCard('validation')}
      </div> : landsat.active ? <div className="mw-bottom-grid mw-sentinel-results-grid">
        <Card id={sentinelSectionId('trend')} title="시계열 통계"><LandsatLongTrend/></Card>
        <Card id={sentinelSectionId('change')} title="장기 변화탐지"><LandsatLongChange/></Card>
      </div> : <div className="mw-bottom-grid">
        <Card title={`${cfg.bottom[0]} (${region})`}>
          <div className="mw-chart-select">
            <select
              aria-label="차트 지표"
              value={draft.chartMetric || (agentId === 'lcluc' ? points[0]?.label || 'Trees (1)' : cfg.kpis[0][0])}
              onChange={e => update('chartMetric', e.target.value)}
            >
              {agentId === 'lcluc' ? (
                <>
                  <optgroup label="9-Class Land Cover">
                    {(points.length ? points : LCLUC_LEGEND_CLASSES).map(cls => (
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
              {provinceScope && yearsShown.length ? `${yearsShown[0]} – ${yearsShown.at(-1)}`
                : `${startYear} – ${endYear}`}
            </small>
          </div>
          {report || bantenResult ? (
            <>
              <LclucRealChart years={yearsShown} points={chartPoints} unit="ha"/>
              {showSnowEvidence && <p className="mw-chart-note">
                Esri 원본의 Snow/ice 분류 면적입니다. 10m 픽셀 1개는 0.01ha이며, 실제 적설·결빙은 확인되지 않았습니다.
              </p>}
            </>
          ) : (
            <EmptyChart legend={cfg.legend} unit={cfg.kpis[0][1]} />
          )}
        </Card>

        <Card title={cfg.bottom[1]}>
          {provinceEnd && bantenResult ? (
            <LclucRealDonut items={bantenResult.classes.map((item, index) => ({
              label: item.name, color: provinceColors[index], valueHa: provinceEnd.areas_ha[item.code],
              pct: 100 * provinceEnd.areas_ha[item.code] / Object.values(provinceEnd.areas_ha).reduce((sum,value) => sum + value, 0),
            }))}/>
          ) : report ? (
            <LclucRealDonut items={points.map(point => ({
              label: point.label, color: point.color, valueHa: point.values[1], pct: area ? 100 * point.values[1] / area : 0,
            }))}/>
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
          {provinceScope ? provinceMatrix() : report ? matrix() : agentId === 'biodiversity' ? (
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
          {report && detail ? (
            <div className="mw-dataset-status"><span>연결 픽셀 집중지역 {report.hotspot_count}개</span>
              {detail.assets.filter(asset => asset.id === 'hotspots').map(asset => <a key={asset.id} href={asset.href}>변화 집중지역 GeoJSON</a>)}
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
      </div>}

      {/* 하단 근거/Job 바 */}
      <div className="mw-evidence-footer">
        <span>
          {agentId === 'lcluc'
            ? report ? `${sourceName} 고정 시험 구역 · 독립 정확도 미측정` : status
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
        {isLcluc && tab === 'result' && !opticalWorkspace && downloads()}
        {children}
      </div>

      {agentId==='lcluc'&&<LclucWorkflowPanel/>}
    </div>
  );
}
