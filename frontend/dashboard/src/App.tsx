import React, { useState } from 'react';
import {
  Waves,
  Play,
  RotateCcw,
  Wifi,
  WifiOff,
  AlertCircle,
  ShieldAlert,
  Activity,
  Compass,
  Ship,
  CheckCircle2,
  FileText,
} from 'lucide-react';
import { CoastGuardAlertPanel } from './components/CoastGuardAlertPanel';
import { useResponses } from './hooks/useResponses';
import { CoastGuardAlert, PipelineResult } from './types';

// Preset Scenarios for Full Pipeline Testing
const SCENARIOS = [
  {
    id: 'chennai_ennore_2017',
    label: 'Ennore / Chennai (2017)',
    lat: 13.23,
    lon: 80.33,
    desc: 'Dawn Kanchipuram vs BW Maple collision in congested coastal waters',
  },
  {
    id: 'mumbai_high_2018',
    label: 'Mumbai High / JNPT',
    lat: 18.95,
    lon: 72.85,
    desc: 'Offshore crude transfer corridor with high tanker traffic',
  },
  {
    id: 'haldia_sundarbans_2018',
    label: 'Haldia / Sundarbans',
    lat: 22.06,
    lon: 88.09,
    desc: 'Ecologically sensitive mangrove Delta with monsoon tidal currents',
  },
  {
    id: 'kochi_tanker_corridor',
    label: 'Kochi Offshore',
    lat: 9.96,
    lon: 76.24,
    desc: 'International east-west tanker route off Arabian Sea',
  },
];

export const App: React.FC = () => {
  const { alerts, latest, connected, error, acknowledge } = useResponses();
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'pipeline' | 'alerts'>('pipeline');

  const selectedAlert: CoastGuardAlert | null =
    (alerts ?? []).find((a) => a.id === selectedAlertId) ?? latest;

  const runFullPipeline = async (scenario: typeof SCENARIOS[number]) => {
    setPipelineLoading(true);
    setPipelineError(null);
    try {
      const res = await fetch('/api/v1/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_name: scenario.label,
          scene_polygon: `POLYGON((${scenario.lon - 0.2} ${scenario.lat - 0.2}, ${scenario.lon + 0.2} ${scenario.lat - 0.2}, ${scenario.lon + 0.2} ${scenario.lat + 0.2}, ${scenario.lon - 0.2} ${scenario.lat + 0.2}, ${scenario.lon - 0.2} ${scenario.lat - 0.2}))`,
          wind_speed: 4.5,
          wind_direction: 45.0,
          captured_at: new Date().toISOString(),
          sim_duration_hours: 12.0,
          num_particles: 50,
        }),
      });

      if (!res.ok) {
        throw new Error(`Pipeline failed with HTTP ${res.status}: ${res.statusText}`);
      }

      const data: PipelineResult = await res.json();
      setPipelineResult(data);
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Pipeline execution failed');
    } finally {
      setPipelineLoading(false);
    }
  };

  const handleAck = async (alertId: string) => {
    try {
      await acknowledge(alertId, 'duty.officer@icg.gov.in');
    } catch (err) {
      console.error('Ack failed:', err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Waves className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-tight">
                  Payodhi
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-950 text-cyan-400 border border-cyan-700/50">
                  7-PHASE ENGINE
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Autonomous Satellite Oil Spill Surveillance & Forensic Attribution
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <nav className="flex bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-xs font-semibold">
              <button
                onClick={() => setActiveTab('pipeline')}
                className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
                  activeTab === 'pipeline'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                7-Phase Pipeline Runner
              </button>
              <button
                onClick={() => setActiveTab('alerts')}
                className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeTab === 'alerts'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                Live ICG Alerts ({alerts?.length ?? 0})
              </button>
            </nav>

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
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8 flex-1 w-full">
        {activeTab === 'pipeline' ? (
          <div className="space-y-6">
            {/* Scenario Launcher */}
            <section className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    End-to-End 7-Phase Pipeline Execution
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Triggers{' '}
                    <code className="text-cyan-300 font-mono">
                      POST /api/v1/pipeline/run
                    </code>{' '}
                    — Ingests SAR scene $\to$ Filters false alarms $\to$ Runs OpenDrift hindcast $\to$ Correlates AIS & dark hulls $\to$ Computes 7-pillar attribution $\to$ Dispatches Coast Guard alert.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {SCENARIOS.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => runFullPipeline(s)}
                    disabled={pipelineLoading}
                    className="flex flex-col text-left p-4 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 hover:border-cyan-500/50 transition-all cursor-pointer group disabled:opacity-50 disabled:cursor-wait"
                  >
                    <div className="flex items-center justify-between w-full mb-2">
                      <span className="font-bold text-xs text-white group-hover:text-cyan-400 transition-colors">
                        {s.label}
                      </span>
                      <Play className="w-3.5 h-3.5 text-cyan-400 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                    <span className="text-[11px] text-slate-400 leading-relaxed">
                      {s.desc}
                    </span>
                    <span className="mt-3 text-[10px] font-mono text-slate-500">
                      {s.lat.toFixed(2)}°N, {s.lon.toFixed(2)}°E
                    </span>
                  </button>
                ))}
              </div>

              {pipelineLoading && (
                <div className="mt-6 p-4 rounded-xl bg-cyan-950/40 border border-cyan-800/60 flex items-center gap-3">
                  <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                  <span className="text-xs text-cyan-200 font-medium">
                    Executing 7-Phase Maritime Pipeline (SAR U-Net $\to$ SAR-UV Filter $\to$ OpenDrift Hindcast $\to$ AIS Correlation $\to$ 7-Pillar Forensic Engine)...
                  </span>
                </div>
              )}

              {pipelineError && (
                <div className="mt-4 p-4 rounded-xl bg-rose-950/50 border border-rose-800 flex items-start gap-3 text-xs text-rose-200">
                  <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                  <span>{pipelineError}</span>
                </div>
              )}
            </section>

            {/* Pipeline Results Summary */}
            {pipelineResult && (
              <section className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
                    <span className="text-[11px] text-slate-400 uppercase font-semibold">
                      Phase 1 & 2: Spill Detection
                    </span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-xl font-bold text-white">
                        {pipelineResult.spill?.area_sq_km.toFixed(2) ?? '0.00'}{' '}
                        <span className="text-xs text-slate-400 font-normal">km²</span>
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-700/50">
                        {((pipelineResult.spill?.confidence_score ?? 0.95) * 100).toFixed(1)}% OIL
                      </span>
                    </div>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
                    <span className="text-[11px] text-slate-400 uppercase font-semibold">
                      Phase 3: Drift Origin
                    </span>
                    <div className="mt-2 text-sm font-mono text-cyan-300">
                      {pipelineResult.drift?.origin_latitude.toFixed(4)}°N,{' '}
                      {pipelineResult.drift?.origin_longitude.toFixed(4)}°E
                    </div>
                    <span className="text-[10px] text-slate-500">
                      12h Reverse Hydrodynamic Window
                    </span>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
                    <span className="text-[11px] text-slate-400 uppercase font-semibold">
                      Phase 4: AIS Candidates
                    </span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-xl font-bold text-white">
                        {pipelineResult.ais?.correlated_vessels_count ?? 0}
                      </span>
                      <span className="text-xs text-slate-400 font-normal">vessels</span>
                      {(pipelineResult.ais?.dark_vessels_detected ?? 0) > 0 && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-700/50">
                          {pipelineResult.ais?.dark_vessels_detected} DARK HULLS
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
                    <span className="text-[11px] text-slate-400 uppercase font-semibold">
                      Phase 7: Coast Guard Action
                    </span>
                    <div className="mt-2 text-sm font-bold text-cyan-400">
                      {pipelineResult.response?.primary_station ?? 'ICG Station'}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      ETA: {pipelineResult.response?.eta_hours?.toFixed(1) ?? '1.2'}h ({pipelineResult.response?.station_distance_km?.toFixed(1)} km)
                    </span>
                  </div>
                </div>

                {/* Candidate Attribution Table */}
                <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 shadow-xl">
                  <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <Ship className="w-4 h-4 text-cyan-400" />
                    Phase 5 & 6: Forensic Attribution & Legal Verdict
                  </h3>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                          <th className="py-3 px-4 font-semibold">Vessel Name & MMSI</th>
                          <th className="py-3 px-4 font-semibold">Type</th>
                          <th className="py-3 px-4 font-semibold">Score / Conf.</th>
                          <th className="py-3 px-4 font-semibold">p-value</th>
                          <th className="py-3 px-4 font-semibold">Stability</th>
                          <th className="py-3 px-4 font-semibold">Capacity Veto</th>
                          <th className="py-3 px-4 font-semibold">Admissibility Verdict</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {(pipelineResult.attribution?.candidates ?? []).map((cand, i) => (
                          <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                            <td className="py-3 px-4 font-bold text-white">
                              {cand.vessel_name}
                              <span className="block font-mono text-[10px] text-slate-500">
                                MMSI: {cand.mmsi}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-300">{cand.vessel_type ?? 'Tanker'}</td>
                            <td className="py-3 px-4">
                              <span className="font-bold text-cyan-300">
                                {cand.total_score.toFixed(1)}
                              </span>
                              <span className="text-[10px] text-slate-400 ml-1">
                                ({cand.confidence_pct.toFixed(0)}%)
                              </span>
                            </td>
                            <td className="py-3 px-4 font-mono text-slate-300">
                              p = {cand.p_value.toFixed(4)}
                            </td>
                            <td className="py-3 px-4 font-mono text-slate-300">
                              {cand.stability_index.toFixed(1)}%
                            </td>
                            <td className="py-3 px-4">
                              {cand.capacity_veto ? (
                                <span className="text-rose-400 font-bold">VETOED</span>
                              ) : (
                                <span className="text-emerald-400 font-medium">PASSED</span>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2.5 py-1 rounded-md font-bold text-[10px] tracking-wide ${
                                  cand.verdict === 'PROSECUTABLE'
                                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/60'
                                    : cand.verdict === 'PERSON_OF_INTEREST'
                                    ? 'bg-amber-950 text-amber-300 border border-amber-700/60'
                                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                                }`}
                              >
                                {cand.verdict}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </section>
            )}
          </div>
        ) : (
          /* Live Coast Guard Alert Desk */
          <div className="space-y-6">
            <CoastGuardAlertPanel
              alert={selectedAlert}
              onAcknowledge={handleAck}
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/60 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-xs text-slate-500">
          <span>Payodhi Defense Technologies — Autonomous Marine Intelligence</span>
          <span>UNCLOS & MARPOL Annex I Admissible Architecture</span>
        </div>
      </footer>
    </div>
  );
};
export default App;
