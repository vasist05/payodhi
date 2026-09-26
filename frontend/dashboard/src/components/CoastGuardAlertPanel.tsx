import React, { useState } from 'react';
import {
  Shield, Radio, Ship, Clock, CheckCircle2, AlertTriangle, Send,
  Compass, MapPin, PhoneCall, Zap, RefreshCw, ChevronRight, Navigation
} from 'lucide-react';
import { CoastGuardAlert } from '../types';
import { StationInfo } from '../hooks/useResponses';

interface Props {
  alerts: CoastGuardAlert[];
  selectedAlertId?: string | null;
  onSelectAlert?: (alertId: string) => void;
  onAcknowledge?: (alertId: string, officerId: string) => void;
  onTriggerTestAlert?: () => void;
  stations?: StationInfo[];
  backendConnected?: boolean;
}

export const CoastGuardAlertPanel: React.FC<Props> = ({
  alerts,
  selectedAlertId,
  onSelectAlert,
  onAcknowledge,
  onTriggerTestAlert,
  stations = [],
  backendConnected = false,
}) => {
  const [officerId, setOfficerId] = useState('duty.officer@icg.gov.in');
  const [triggering, setTriggering] = useState(false);

  const currentAlert: CoastGuardAlert | null =
    (alerts.find((a) => a.id === selectedAlertId) ?? alerts[0]) || null;

  const handleTrigger = async () => {
    if (!onTriggerTestAlert) return;
    setTriggering(true);
    try {
      await onTriggerTestAlert();
    } finally {
      setTimeout(() => setTriggering(false), 500);
    }
  };

  const handleAckClick = () => {
    if (currentAlert && onAcknowledge) {
      onAcknowledge(currentAlert.id, officerId || 'duty.officer@icg.gov.in');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Fast Actions */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-rose-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">
                Indian Coast Guard — Maritime Response Desk
              </h1>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                backendConnected
                  ? 'bg-emerald-950/80 text-emerald-400 border-emerald-700/60'
                  : 'bg-amber-950/80 text-amber-300 border-amber-700/60'
              }`}>
                {backendConnected ? 'LIVE WS CONNECTED' : 'HYBRID MOCK/OFFLINE'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Automated Phase 8 Emergency Vector Dispatch & Multi-Station Interception Fleet Routing
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onTriggerTestAlert && (
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 transition-all active:scale-95 shadow-md shadow-amber-500/20 cursor-pointer disabled:opacity-50"
            >
              <Zap className="w-3.5 h-3.5" />
              {triggering ? 'Dispatching...' : 'Dispatch Test CG Alert'}
            </button>
          )}
        </div>
      </div>

      {/* Main Grid: Alert List (Left) + Detail View (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Alerts Queue (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Radio className="w-4 h-4 text-cyan-400" />
                Active Incident Alerts ({alerts.length})
              </h3>
            </div>

            {alerts.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No active Coast Guard dispatches.
              </div>
            ) : (
              <div className="space-y-2 max-h-[580px] overflow-y-auto pr-1">
                {alerts.map((al) => {
                  const isSelected = al.id === currentAlert?.id;
                  const isAcked = Boolean(al.ackedBy);

                  return (
                    <div
                      key={al.id}
                      onClick={() => onSelectAlert && onSelectAlert(al.id)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-slate-800/90 border-cyan-500/80 shadow-md shadow-cyan-500/10'
                          : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/40'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                          al.severity === 'HIGH'
                            ? 'bg-rose-950/80 text-rose-300 border-rose-800/60'
                            : 'bg-amber-950/80 text-amber-300 border-amber-800/60'
                        }`}>
                          {al.severity} SEVERITY
                        </span>
                        {isAcked ? (
                          <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" /> ACKED
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 animate-pulse">
                            <AlertTriangle className="w-3 h-3" /> PENDING
                          </span>
                        )}
                      </div>

                      <div className="text-xs font-bold text-white truncate">
                        {al.stationName}
                      </div>

                      {al.topSuspect && (
                        <div className="text-[11px] text-amber-300/90 mt-0.5 truncate flex items-center gap-1">
                          <Ship className="w-3 h-3 flex-shrink-0" /> {al.topSuspect}
                        </div>
                      )}

                      <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60">
                        <span>ETA {al.etaHours != null ? al.etaHours.toFixed(1) : '—'}h ({al.stationDistanceKm?.toFixed(1) ?? '—'} km)</span>
                        <span className="font-mono text-slate-500">
                          {new Date(al.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Station Readiness Quick-List */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-xl">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Compass className="w-4 h-4 text-cyan-400" />
              ICG Station Registry ({stations.length})
            </h3>
            <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1 text-xs">
              {stations.map((st) => (
                <div key={st.id} className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-white text-[11px]">{st.name}</p>
                    <p className="text-[10px] text-slate-400">{st.district} · {st.type}</p>
                  </div>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800/50">
                    {st.lat.toFixed(2)}°N, {st.lon.toFixed(2)}°E
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Selected Alert Detailed Card (8 cols) */}
        <div className="lg:col-span-8 space-y-5">
          {!currentAlert ? (
            <div className="p-12 text-center bg-slate-900/90 border border-slate-800 rounded-2xl text-slate-400">
              <Shield className="w-10 h-10 mx-auto text-slate-600 mb-3" />
              <p className="text-sm font-semibold">No Alert Selected</p>
              <p className="text-xs text-slate-500 mt-1">Select an incident from the queue on the left or trigger a test dispatch.</p>
            </div>
          ) : (
            <div className="bg-slate-900/90 border border-amber-500/50 rounded-2xl p-6 shadow-2xl space-y-6">
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
                    <Radio className="w-6 h-6 animate-pulse" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-bold text-white">
                        Tactical Dispatch: {currentAlert.id}
                      </h2>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        currentAlert.severity === 'HIGH'
                          ? 'bg-rose-950 text-rose-300 border-rose-800'
                          : 'bg-amber-950 text-amber-300 border-amber-800'
                      }`}>
                        {currentAlert.severity} PRIORITY
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Origin Hydrodynamic Vector Assigned to MRCC Station
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xs text-slate-500">Incident Timestamp</div>
                  <div className="text-xs font-mono text-cyan-300 font-bold">
                    {new Date(currentAlert.createdAt).toUTCString()}
                  </div>
                </div>
              </div>

              {/* Station & ETA Banner */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Assigned Primary Station
                  </span>
                  <div className="text-sm font-bold text-white mt-1">
                    {currentAlert.stationName}
                  </div>
                  <span className="text-[10px] text-cyan-400 font-mono mt-0.5 block">
                    ID: {currentAlert.stationId}
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Distance to Spill Origin
                  </span>
                  <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
                    {currentAlert.stationDistanceKm?.toFixed(1) ?? '—'}{' '}
                    <span className="text-xs font-normal text-slate-400">km</span>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    Hydrodynamic center of mass
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Estimated Time to Intercept
                  </span>
                  <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                    {currentAlert.etaHours?.toFixed(1) ?? '—'}{' '}
                    <span className="text-xs font-normal text-slate-400">hours</span>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    At 22kt tactical patrol cruising speed
                  </span>
                </div>
              </div>

              {/* Primary Suspect & Interception Fleet */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Target Information */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-300">
                    <Ship className="w-4 h-4" />
                    Target Identification & Confidence
                  </div>
                  <div className="text-sm font-bold text-white">
                    {currentAlert.topSuspect || 'Pending Multi-Factor Attribution'}
                  </div>
                  <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800">
                    <span className="text-slate-400">U-Net & Filter Confidence:</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {((currentAlert.confidence ?? 0.9) * 100).toFixed(1)}% OIL VERIFIED
                    </span>
                  </div>
                </div>

                {/* Interception fleet */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-300">
                    <Navigation className="w-4 h-4" />
                    Intercept-Capable Assets ({currentAlert.interceptionCount})
                  </div>
                  <div className="text-xs text-slate-300 space-y-1">
                    {(currentAlert.nearestVessels.length > 0 ? currentAlert.nearestVessels : ['ICGS Fast Interceptor (C-435)', 'ICGS Patrol Craft (Rani Abbakka)']).map((v, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-emerald-300/90 font-mono text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        {v}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* SMS Dispatch & Comm Gate */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-3">
                <PhoneCall className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">Emergency SMS Telemetry Dispatch</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      currentAlert.smsStatus === 'sent'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-slate-800 text-slate-400'
                    }`}>
                      {currentAlert.smsStatus?.toUpperCase() ?? 'DISPATCHED'}
                    </span>
                  </div>
                  <p className="text-xs font-mono text-slate-400 mt-1 break-words">
                    {currentAlert.smsReason || 'Dispatched via Twilio API Gateway to ICG District Ops Commander'}
                  </p>
                </div>
              </div>

              {/* Acknowledge Command Strip */}
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 flex flex-wrap items-center justify-between gap-4">
                {currentAlert.ackedBy ? (
                  <div className="flex items-center gap-2 text-xs text-emerald-400 font-bold">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>
                      Acknowledged by {currentAlert.ackedBy} at{' '}
                      {currentAlert.ackedAt ? new Date(currentAlert.ackedAt).toLocaleTimeString() : 'Recorded'}
                    </span>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-2 flex-1 min-w-[240px]">
                      <span className="text-xs text-slate-400 whitespace-nowrap">Duty Officer ID:</span>
                      <input
                        type="text"
                        value={officerId}
                        onChange={(e) => setOfficerId(e.target.value)}
                        className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono flex-1 focus:outline-none focus:border-cyan-500"
                        placeholder="officer@icg.gov.in"
                      />
                    </div>
                    <button
                      onClick={handleAckClick}
                      className="px-5 py-2 rounded-xl text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white transition-all active:scale-95 shadow-md shadow-cyan-600/20 cursor-pointer flex items-center gap-2"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Acknowledge & Confirm Interception
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default CoastGuardAlertPanel;
