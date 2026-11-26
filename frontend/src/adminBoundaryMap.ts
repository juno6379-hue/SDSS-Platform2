import type { Map as LibreMap } from 'maplibre-gl';
import { readAdminBoundary } from './lclucExplorerData';
import type { AdminBoundary } from './lclucExplorerData';

const sourceId = 'onemap-admin';
export const adminBoundaryStartLayer = 'onemap-admin-hit';

let allBoundaries: Promise<AdminBoundary> | undefined;
export function allAdminBoundaries() {
  allBoundaries ??= readAdminBoundary().catch(error => {
    allBoundaries = undefined;
    throw error;
  });
  return allBoundaries;
}

const outlines = [
  { id: 'onemap-district-casing', level: 'district', color: '#18303f', width: 3.5, minzoom: 6 },
  { id: 'onemap-district-outline', level: 'district', color: '#ffdc72', width: 1.6, minzoom: 6 },
  { id: 'onemap-province-casing', level: 'province', color: '#18303f', width: 5, minzoom: 0 },
  { id: 'onemap-province-outline', level: 'province', color: '#5fe3ff', width: 2.5, minzoom: 0 },
] as const;

export function drawAdminBoundaries(map: LibreMap, data: AdminBoundary, visible = true) {
  const visibility = visible ? 'visible' : 'none';
  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, { type: 'geojson', data: data.geojson });
    map.addSource('onemap-province-labels', { type: 'geojson', data: data.province_labels });
    map.addLayer({
      id: adminBoundaryStartLayer, type: 'fill', source: sourceId,
      filter: ['==', ['get', 'level'], 'district'],
      paint: { 'fill-color': '#ffffff', 'fill-opacity': 0 },
    });
    for (const line of outlines) {
      map.addLayer({
        id: line.id, type: 'line', source: sourceId, minzoom: line.minzoom,
        filter: ['==', ['get', 'level'], line.level],
        paint: { 'line-color': line.color, 'line-width': line.width },
      });
    }
    map.addLayer({
      id: 'onemap-province-name', type: 'symbol', source: 'onemap-province-labels', maxzoom: 10,
      layout: {
        'text-field': ['get', 'name'], 'text-font': ['Arial Bold'],
        'text-variable-anchor': ['center', 'top', 'bottom', 'left', 'right'],
        'text-radial-offset': 0.7,
        'text-size': ['interpolate', ['linear'], ['zoom'], 4, 10, 8, 15],
      },
      paint: { 'text-color': '#e6fbff', 'text-halo-color': '#14283b', 'text-halo-width': 1.7 },
    });
    map.addLayer({
      id: 'onemap-district-name', type: 'symbol', source: sourceId, minzoom: 8,
      filter: ['==', ['get', 'level'], 'district'],
      layout: {
        'text-field': ['get', 'name'], 'text-font': ['Arial Bold'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 8, 11, 14, 14],
      },
      paint: { 'text-color': '#fff5ce', 'text-halo-color': '#14283b', 'text-halo-width': 1.7 },
    });
  }
  for (const layer of [adminBoundaryStartLayer, ...outlines.map(line => line.id), 'onemap-province-name', 'onemap-district-name']) {
    map.setLayoutProperty(layer, 'visibility', visibility);
  }
}

export function afterAdminStyle(map: LibreMap, draw: () => void) {
  const runWhenReady = () => {
    if (!map.getStyle()?.layers.some(layer => map.getLayer(layer.id))) return;
    map.off('styledata', runWhenReady);
    draw();
  };
  map.on('styledata', runWhenReady);
  runWhenReady();
  return () => { map.off('styledata', runWhenReady); };
}

export function showAdminBoundaries(map: LibreMap, onLoaded?: (loaded: boolean) => void) {
  let active = true;
  let removeWait: (() => void) | undefined;
  void allAdminBoundaries().then(data => {
    if (!active) return;
    removeWait = afterAdminStyle(map, () => {
      drawAdminBoundaries(map, data);
      onLoaded?.(true);
    });
  }).catch(() => { if (active) onLoaded?.(false); });
  return () => { active = false; removeWait?.(); };
}
