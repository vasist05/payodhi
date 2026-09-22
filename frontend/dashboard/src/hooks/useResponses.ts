/**
 * Phase 8 — live Coast Guard alert stream.
 *
 * Opens a WebSocket to /ws/responses (proxied through Vite to the backend)
 * and keeps the latest alert + full history in state. Falls back to a REST
 * fetch of /api/responses on mount so the panel has content immediately,
 * even before the first WS event arrives.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { CoastGuardAlert } from '../types';

interface UseResponsesResult {
  alerts: CoastGuardAlert[];
  latest: CoastGuardAlert | null;
  connected: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  acknowledge: (alertId: string, ackedBy: string) => Promise<void>;
}

// Backend API returns snake_case. Normalize once here.
function normalizeAlert(raw: any): CoastGuardAlert {
  return {
    id: raw.id,
    stationId: raw.station_id,
    stationName: raw.station_name,
    stationDistanceKm: raw.station_distance_km,
    backupStations: raw.backup_stations ?? [],
    severity: raw.severity,
    confidence: raw.confidence,
    topSuspect: raw.top_suspect,
    interceptionCount: raw.interception_count,
    nearestVessels: raw.nearest_vessels ?? [],
    etaHours: raw.eta_hours,
    createdAt: raw.created_at,
    ackedBy: raw.acked_by,
    ackedAt: raw.acked_at,
    smsStatus: raw.sms_status,
    smsReason: raw.sms_reason,
  };
}

export function useResponses(): UseResponsesResult {
  const [alerts, setAlerts] = useState<CoastGuardAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/responses');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const normalized: CoastGuardAlert[] = (data.alerts ?? []).map(normalizeAlert);
      setAlerts(normalized);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch alert history');
    }
  }, []);

  const acknowledge = useCallback(async (alertId: string, ackedBy: string) => {
    const res = await fetch(`/api/responses/${alertId}/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acked_by: ackedBy }),
    });
    if (!res.ok) throw new Error(`Ack failed: HTTP ${res.status}`);

    // Optimistic update — the WS will also broadcast the ack frame.
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId
          ? { ...a, ackedBy, ackedAt: new Date().toISOString() }
          : a,
      ),
    );
  }, []);

  // Initial REST load
  useEffect(() => {
    refresh();
  }, [refresh]);

  // WebSocket connection with basic reconnect
  useEffect(() => {
    let closedByUs = false;

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsUrl = `${proto}://${window.location.host}/ws/responses`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'alert') {
            const incoming = normalizeAlert(msg.data);
            setAlerts((prev) => {
              if (prev.some((a) => a.id === incoming.id)) return prev;
              return [incoming, ...prev];
            });
          } else if (msg.type === 'ack') {
            setAlerts((prev) =>
              prev.map((a) =>
                a.id === msg.id
                  ? { ...a, ackedBy: msg.acked_by, ackedAt: msg.acked_at }
                  : a,
              ),
            );
          }
        } catch (err) {
          console.warn('[useResponses] bad WS frame:', evt.data);
        }
      };

      ws.onerror = () => {
        setError('WebSocket error');
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!closedByUs) {
          // Reconnect after 2s
          reconnectRef.current = window.setTimeout(connect, 2000);
        }
      };
    };

    connect();

    return () => {
      closedByUs = true;
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, []);

  return {
    alerts,
    latest: alerts[0] ?? null,
    connected,
    error,
    refresh,
    acknowledge,
  };
}
