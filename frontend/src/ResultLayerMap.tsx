import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { showAdminBoundaries } from './adminBoundaryMap';

type Bounds = [number, number, number, number];

export default function ResultLayerMap({ href, bounds, title }: { href: string; bounds: Bounds; title: string }) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState('지도 레이어를 읽는 중…');

  useEffect(() => {
    const host = container.current;
    if (!host) return;
    const controller = new AbortController();
    let map: maplibregl.Map | undefined;
    let removeAdmin: (() => void) | undefined;
    async function render() {
      const response = await fetch(href, { signal: controller.signal });
      if (!response.ok) throw new Error('지도 레이어를 열 수 없습니다.');
      const geometry = await response.json();
      if (controller.signal.aborted) return;
      map = new maplibregl.Map({
        container: host!,
        attributionControl: false,
        style: {
          version: 8,
          sources: { result: { type: 'geojson', data: geometry } },
          layers: [
            { id: 'background', type: 'background', paint: { 'background-color': '#e9f0f7' } },
            { id: 'areas', source: 'result', type: 'fill', paint: { 'fill-color': '#147ab7', 'fill-opacity': 0.42 } },
            { id: 'outlines', source: 'result', type: 'line', paint: { 'line-color': '#145380', 'line-width': 2 } },
            { id: 'points', source: 'result', type: 'circle', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-color': '#14628e', 'circle-radius': 2 } },
          ],
        },
        bounds,
        fitBoundsOptions: { padding: 20, maxZoom: 14, duration: 0 },
      });
      removeAdmin = showAdminBoundaries(map);
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      map.once('load', () => setStatus(''));
      map.on('error', () => setStatus('지도 미리보기를 표시할 수 없습니다.'));
    }
    setStatus('지도 레이어를 읽는 중…');
    void render().catch(() => {
      if (!controller.signal.aborted) setStatus('지도 미리보기를 표시할 수 없습니다.');
    });
    return () => { controller.abort(); removeAdmin?.(); map?.remove(); };
  }, [href, bounds]);

  return <><div className="common-catalog-map" ref={container} aria-label={title} data-testid="common-catalog-map"/>{status && <p role="status">{status}</p>}</>;
}
