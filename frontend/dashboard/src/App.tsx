import React, { useState } from 'react';
import { Waves, Play, RotateCcw, Wifi, WifiOff, AlertCircle } from 'lucide-react';
import { CoastGuardAlertPanel } from './components/CoastGuardAlertPanel';
import { useResponses } from './hooks/useResponses';
import { CoastGuardAlert } from './types';

// Demo trigger presets — coordinates map to specific stations.
const PRESETS = [
  { label: 'Ennore / Chennai', lat: 13.23, lon: 80.33, id: 'ENNORE_DEMO' },
  { label: 'Kochi', lat: 9.96, lon: 76.24, id: 'KOCHI_DEMO' },
  { label: 'Mumbai / JNPT', lat: 18.95, lon: 72.85, id: 'MUMBAI_DEMO' },
  { label: 'Haldia', lat: 22.06, lon: 88.09, id: 'HALDIA_DEMO' },
];

export const App: React.FC = () => {
  const { alerts, latest, connected, error, acknowledge } = useResponses();
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

  const selectedAlert: CoastGuardAlert | null =
    (alerts ?? []).find((a) => a.id === selectedAlertId) ?? latest;

  const triggerAlert = async (preset: typeof PRESETS[number]) => {
    setIsTriggering(true);
    setTriggerError(null);
    try {
      const res = await fetch('/api/responses/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_id: preset.id,
          lat: preset.lat,
          lon: preset.lon,
          confidence: 0.96,
          top_suspect_name: 'DAWN KANCHIPURAM',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.status === 'suppressed') {
        setTriggerError(
          `Suppressed: ${data.reason}${
            data.station_id ? ` (${data.station_id})` : ''
          }`,
        );
      }
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : 'Trigger failed');
    } finally {
      setIsTriggering(false);
    }
  };

  const handleAck = async (alertId: string) => {
    try {
      await acknowledge(alertId, 'duty.officer@icg');
    } catch (err) {
      console.error('Ack failed:', err);
    }
  };

  return (
    <div className="min-h-screen bg-tactical-dark text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-600 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-600/20">
              <Waves className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-tight">
                Payodhi — Phase 8
              </h1>
              <p className="text-xs text-slate-400">
                Coast Guard Alert & Interception Fleet Availability
              </p>
            </div>
          </div>

          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              connected
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                : 'bg-rose-950/60 text-rose-300 border-rose-700/60'
            }`}
          >
            {connected ? (
              <Wifi className="w-3.5 h-3.5" />
            ) : (
              <WifiOff className="w-3.5 h-3.5" />
            )}
            <span>{connected ? 'WS CONNECTED' : 'WS OFFLINE'}</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* Demo controls */}
        <section className="bg-slate-900 rounded-2xl border border-slate-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white">Demo Triggers</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Fires{' '}
                <code className="text-cyan-400 font-mono">
                  POST /api/responses/test
                </code>{' '}
                with real dispatch path. Watch the panel light up via WebSocket.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => triggerAlert(preset)}
                disabled={isTriggering}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-bold transition-all active:scale-95 disabled:opacity-50 disabled:cursor-wait shadow-lg shadow-cyan-900/20 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5" />
                {preset.label}
              </button>
            ))}
          </div>

          {triggerError && (
            <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-950/50 border border-amber-700/60 text-xs text-amber-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{triggerError}</span>
            </div>
          )}

          {error && (
            <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-rose-950/50 border border-rose-700/60 text-xs text-rose-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>WS error: {error}</span>
            </div>
          )}

          <p className="text-xs text-slate-500 mt-3">
            <RotateCcw className="w-3 h-3 inline mr-1" /> If a trigger is
            suppressed with <code className="text-slate-300">reason: "cooldown"</code>, delete{' '}
            <code className="text-slate-300 ml-1">
              backend/notification/alerts.db
            </code>{' '}
            and retry.
          </p>
        </section>

        {/* Current alert */}
        <section>
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            Latest Alert
          </h2>
          <CoastGuardAlertPanel alert={selectedAlert} onAcknowledge={handleAck} />
        </section>

        {/* Alert history */}
        {(alerts ?? []).length > 1 && (
          <section>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
              History ({(alerts ?? []).length})
            </h2>
            <div className="space-y-2">
              {(alerts ?? []).slice(1).map((a) => {
                const eta = a.etaHours != null ? Number(a.etaHours).toFixed(1) : '—';
                const time = a.createdAt ? new Date(a.createdAt).toLocaleTimeString() : '';
                return (
                  <button
                    key={a.id}
                    onClick={() => setSelectedAlertId(a.id)}
                    className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer ${
                      selectedAlert?.id === a.id
                        ? 'bg-slate-800 border-cyan-600'
                        : 'bg-slate-900 border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">
                        {a.stationName}
                      </span>
                      <span className="text-slate-400 font-mono">
                        {time}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {a.interceptionCount ?? 0} assets · ETA {eta}h ·{' '}
                      <span
                        className={
                          a.severity === 'HIGH'
                            ? 'text-rose-300'
                            : 'text-amber-300'
                        }
                      >
                        {a.severity}
                      </span>
                      {a.ackedBy && (
                        <span className="ml-2 text-emerald-400">• acked</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {/* Empty state */}
        {(alerts ?? []).length === 0 && !error && (
          <div className="text-center py-12 text-slate-500 text-sm">
            No alerts yet. Fire a demo trigger above to see the flow.
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
