import React from 'react';
import { Shield, Radio, Ship, Clock, CheckCircle2, Waves } from 'lucide-react';
import { CoastGuardAlert } from '../types';

interface Props {
  alert: CoastGuardAlert | null | undefined;
  onAcknowledge?: (alertId: string) => void;
}

export const CoastGuardAlertPanel: React.FC<Props> = ({ alert, onAcknowledge }) => {
  if (!alert) {
    return (
      <div className="p-4 bg-slate-900 rounded-lg border border-slate-700">
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <Shield className="w-4 h-4" />
          <span>No Coast Guard alert — scene verified clean or below alert threshold.</span>
        </div>
      </div>
    );
  }

  const isAcked = Boolean(alert.ackedBy);

  return (
    <div className="p-5 bg-slate-900 rounded-2xl border border-amber-600/60 shadow-xl shadow-amber-950/30">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold flex items-center gap-2 text-amber-300">
          <Shield className="w-5 h-5" />
          Coast Guard Alert Dispatched
        </h2>
        <span
          className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
            alert.severity === 'HIGH'
              ? 'bg-red-950 text-red-300 border-red-800'
              : 'bg-amber-950 text-amber-300 border-amber-800'
          }`}
        >
          {alert.severity}
        </span>
      </div>

      {/* Primary station */}
      <div className="space-y-3 text-sm">
        <div className="flex items-start gap-3 bg-slate-800/60 p-3 rounded-xl border border-slate-700/60">
          <Radio className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-white text-sm">{alert.stationName}</p>
            <p className="text-xs text-slate-400 mt-0.5">
              {alert.stationDistanceKm.toFixed(1)} km from spill origin · ETA{' '}
              {alert.etaHours.toFixed(1)} h
            </p>
          </div>
        </div>

        {/* Backup stations */}
        {alert.backupStations.length > 0 && (
          <p className="text-xs text-slate-400 px-1">
            <span className="text-slate-500">Backup stations:</span>{' '}
            {alert.backupStations.join(', ')}
          </p>
        )}

        {/* Interception count */}
        <div className="flex items-center gap-2 bg-emerald-950/40 border border-emerald-800/60 p-3 rounded-xl">
          <Ship className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-bold text-emerald-300">
              {alert.interceptionCount} interception-capable assets within 100 km
            </p>
            {alert.nearestVessels.length > 0 && (
              <p className="text-xs text-emerald-200/70 mt-0.5">
                Nearest: {alert.nearestVessels.slice(0, 3).join(', ')}
              </p>
            )}
          </div>
        </div>

        {/* Top suspect */}
        {alert.topSuspect && (
          <p className="text-xs text-amber-300 px-1">
            <span className="text-slate-500">Primary suspect:</span> {alert.topSuspect}
          </p>
        )}

        {/* Confidence */}
        <div className="flex items-center justify-between text-xs px-1 pt-1">
          <span className="text-slate-500">Detection confidence</span>
          <span className="font-mono text-cyan-300 font-bold">
            {(alert.confidence * 100).toFixed(1)}%
          </span>
        </div>

        {/* SMS status — useful during demo */}
        {alert.smsStatus && (
          <div className="flex items-center justify-between text-xs px-1">
            <span className="text-slate-500">SMS dispatch</span>
            <span
              className={`font-mono font-bold ${
                alert.smsStatus === 'sent'
                  ? 'text-emerald-300'
                  : alert.smsStatus === 'error'
                  ? 'text-rose-300'
                  : 'text-slate-400'
              }`}
            >
              {alert.smsStatus}
              {alert.smsReason ? ` (${alert.smsReason})` : ''}
            </span>
          </div>
        )}

        {/* Timestamp + ack */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-800 mt-1">
          <p className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock className="w-3 h-3" /> {new Date(alert.createdAt).toUTCString()}
          </p>
          {isAcked ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" /> Acked by {alert.ackedBy}
            </span>
          ) : onAcknowledge ? (
            <button
              onClick={() => onAcknowledge(alert.id)}
              className="text-xs font-bold px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition-colors active:scale-95"
            >
              Acknowledge
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
};
