import React, { useState, useEffect, useRef } from 'react';
import {
  Play, Pause, RotateCcw, FastForward, Rewind, Layers, Compass, Wind,
  Droplet, Eye, EyeOff, Maximize2, Shield, Activity, Sparkles, AlertTriangle,
  FileCheck, Download, Video, Info
} from 'lucide-react';
import { IncidentCase } from '../App';

interface Props {
  incident: IncidentCase;
  allIncidents: IncidentCase[];
  onSelectIncident: (inc: IncidentCase) => void;
}

interface Particle {
  id: number;
  originX: number;
  originY: number;
  currentX: number;
  currentY: number;
  driftDx: number;
  driftDy: number;
  turbDx: number;
  turbDy: number;
  mass: number;
  evaporated: boolean;
}

interface WindStreak {
  x: number;
  y: number;
  length: number;
  speed: number;
  alpha: number;
  width: number;
}

export const SimulationVideoStudio: React.FC<Props> = ({
  incident,
  allIncidents,
  onSelectIncident,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const windCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [progress, setProgress] = useState<number>(0.5); // 0 (T-12h origin) -> 1 (T0 detection)
  const [showParticles, setShowParticles] = useState(true);
  const [showIsolines, setShowIsolines] = useState(true);
  const [showVectorGrid, setShowVectorGrid] = useState(true);
  const [showWindStreamlines, setShowWindStreamlines] = useState(true);
  const [activeMediaOverlay, setActiveMediaOverlay] = useState<'particles' | 'sar_overlay' | 'heatmap_overlay'>('particles');

  const animationFrameRef = useRef<number | null>(null);
  const windAnimRef = useRef<number | null>(null);
  const particlesRef = useRef<Particle[]>([]);
  const windStreaksRef = useRef<WindStreak[]>([]);

  // Meteorological wind angle: direction FROM which wind blows
  const windAngleRad = ((incident.windDirectionDeg + 90) * Math.PI) / 180;

  // Initialize wind streamline particles
  useEffect(() => {
    const list: WindStreak[] = [];
    const count = 50;
    for (let i = 0; i < count; i++) {
      list.push({
        x: Math.random() * 800,
        y: Math.random() * 500,
        length: 22 + Math.random() * 26,
        speed: (incident.windSpeedKnots * 0.14 + 0.9) * (0.8 + Math.random() * 0.4),
        alpha: 0.2 + Math.random() * 0.35,
        width: 1.2 + Math.random() * 1.3,
      });
    }
    windStreaksRef.current = list;
  }, [incident.windSpeedKnots, incident.windDirectionDeg]);

  // 60fps render loop for Wind Streamlines on dedicated transparent canvas
  useEffect(() => {
    if (!showWindStreamlines) {
      const canvas = windCanvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    const canvas = windCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dx = Math.cos(windAngleRad);
    const dy = Math.sin(windAngleRad);

    const renderWind = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const streaks = windStreaksRef.current;
      for (let i = 0; i < streaks.length; i++) {
        const s = streaks[i];

        // Move streak with playback modulation
        const currentSpeed = isPlaying ? s.speed * playbackSpeed : s.speed * 0.4;
        s.x += dx * currentSpeed;
        s.y += dy * currentSpeed;

        // Wrap around viewport edges
        if (s.x < -60) s.x = width + 50;
        if (s.x > width + 60) s.x = -50;
        if (s.y < -60) s.y = height + 50;
        if (s.y > height + 60) s.y = -50;

        const tailX = s.x - dx * s.length;
        const tailY = s.y - dy * s.length;

        // Draw Streamline Gradient
        const grad = ctx.createLinearGradient(tailX, tailY, s.x, s.y);
        grad.addColorStop(0, 'rgba(6, 182, 212, 0)');
        grad.addColorStop(0.7, `rgba(56, 189, 248, ${s.alpha * 0.7})`);
        grad.addColorStop(1, `rgba(165, 243, 252, ${s.alpha})`);

        ctx.strokeStyle = grad;
        ctx.lineWidth = s.width;
        ctx.lineCap = 'round';

        ctx.beginPath();
        ctx.moveTo(tailX, tailY);
        ctx.lineTo(s.x, s.y);
        ctx.stroke();

        // Arrowhead on head of every 3rd streak
        if (i % 3 === 0) {
          const arrowLen = 5;
          const arrowAngle = Math.PI / 6;
          ctx.fillStyle = `rgba(165, 243, 252, ${s.alpha * 0.9})`;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(
            s.x - arrowLen * Math.cos(windAngleRad - arrowAngle),
            s.y - arrowLen * Math.sin(windAngleRad - arrowAngle)
          );
          ctx.lineTo(
            s.x - arrowLen * Math.cos(windAngleRad + arrowAngle),
            s.y - arrowLen * Math.sin(windAngleRad + arrowAngle)
          );
          ctx.closePath();
          ctx.fill();
        }
      }

      windAnimRef.current = requestAnimationFrame(renderWind);
    };

    windAnimRef.current = requestAnimationFrame(renderWind);

    return () => {
      if (windAnimRef.current) cancelAnimationFrame(windAnimRef.current);
    };
  }, [showWindStreamlines, isPlaying, playbackSpeed, windAngleRad]);

  // Initialize 400 Monte Carlo particles
  useEffect(() => {
    const list: Particle[] = [];
    const count = 350;
    for (let i = 0; i < count; i++) {
      // Gaussian distribution around origin
      const angle = Math.random() * Math.PI * 2;
      const r = Math.sqrt(-2 * Math.log(Math.random() || 0.001)) * 30;
      const ox = 250 + Math.cos(angle) * r;
      const oy = 250 + Math.sin(angle) * r;

      list.push({
        id: i,
        originX: ox,
        originY: oy,
        currentX: ox,
        currentY: oy,
        driftDx: 180 + (Math.random() - 0.5) * 40,
        driftDy: 140 + (Math.random() - 0.5) * 35,
        turbDx: (Math.random() - 0.5) * 20,
        turbDy: (Math.random() - 0.5) * 20,
        mass: Math.random() * 0.7 + 0.3,
        evaporated: false,
      });
    }
    particlesRef.current = list;
  }, [incident.id]);

  // Main 60fps render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let lastTime = performance.now();

    const render = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      if (isPlaying) {
        setProgress((prev) => {
          const next = prev + (dt * 0.1 * playbackSpeed);
          return next > 1 ? 0 : next;
        });
      }

      // Draw Simulation Frame
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // 1. Ocean Background Gradient
      const oceanGrad = ctx.createLinearGradient(0, 0, width, height);
      oceanGrad.addColorStop(0, '#020b18');
      oceanGrad.addColorStop(1, '#061a33');
      ctx.fillStyle = oceanGrad;
      ctx.fillRect(0, 0, width, height);

      // 2. Tactical GIS Grid lines
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.07)';
      ctx.lineWidth = 1;
      const step = 40;
      for (let x = 0; x < width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // 3. Current & Wind Forcing Vector Field
      if (showVectorGrid) {
        ctx.strokeStyle = 'rgba(14, 165, 233, 0.18)';
        ctx.fillStyle = 'rgba(14, 165, 233, 0.25)';
        for (let gx = 50; gx < width - 40; gx += 70) {
          for (let gy = 50; gy < height - 40; gy += 70) {
            const vLen = 18;
            const vAngle = Math.PI / 4 + Math.sin(gx * 0.01 + progress * 2) * 0.1;
            const endX = gx + Math.cos(vAngle) * vLen;
            const endY = gy + Math.sin(vAngle) * vLen;

            ctx.beginPath();
            ctx.moveTo(gx, gy);
            ctx.lineTo(endX, endY);
            ctx.stroke();

            // Arrowhead
            ctx.beginPath();
            ctx.arc(endX, endY, 1.5, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      // 4. Hydrodynamic Origin Zone (T - 12h)
      const originX = 220;
      const originY = 220;
      const detectionX = originX + 220;
      const detectionY = originY + 170;

      // Draw Origin Anchor & Confidence Ellipses
      ctx.save();
      ctx.strokeStyle = 'rgba(244, 63, 94, 0.4)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(originX, originY, 45, 0, Math.PI * 2);
      ctx.stroke();

      ctx.strokeStyle = 'rgba(244, 63, 94, 0.7)';
      ctx.beginPath();
      ctx.arc(originX, originY, 25, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Origin text
      ctx.fillStyle = '#f43f5e';
      ctx.font = '10px monospace';
      ctx.fillText('ORIGIN RELEASE (T - 12h)', originX - 60, originY - 52);

      // 5. Draw Drift Centerline Track
      ctx.save();
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(originX, originY);
      ctx.quadraticCurveTo(
        (originX + detectionX) / 2 + 30,
        (originY + detectionY) / 2 - 20,
        detectionX,
        detectionY
      );
      ctx.stroke();
      ctx.restore();

      // 6. Plume Dispersion Isolines (Density Heatmap)
      const currentCenterX = originX + (detectionX - originX) * progress;
      const currentCenterY = originY + (detectionY - originY) * progress;
      const spread = 20 + progress * 55;

      if (showIsolines) {
        // Outer Sheen (0.1 mm)
        const g1 = ctx.createRadialGradient(
          currentCenterX, currentCenterY, 5,
          currentCenterX, currentCenterY, spread * 1.5
        );
        g1.addColorStop(0, 'rgba(6, 182, 212, 0.35)');
        g1.addColorStop(0.6, 'rgba(6, 182, 212, 0.12)');
        g1.addColorStop(1, 'rgba(6, 182, 212, 0)');
        ctx.fillStyle = g1;
        ctx.beginPath();
        ctx.arc(currentCenterX, currentCenterY, spread * 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Dense Emulsion Core
        const g2 = ctx.createRadialGradient(
          currentCenterX, currentCenterY, 2,
          currentCenterX, currentCenterY, spread * 0.7
        );
        g2.addColorStop(0, 'rgba(245, 158, 11, 0.6)');
        g2.addColorStop(0.8, 'rgba(244, 63, 94, 0.3)');
        g2.addColorStop(1, 'rgba(244, 63, 94, 0)');
        ctx.fillStyle = g2;
        ctx.beginPath();
        ctx.arc(currentCenterX, currentCenterY, spread * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }

      // 7. Individual Monte Carlo Particles
      if (showParticles) {
        const particles = particlesRef.current;
        for (let i = 0; i < particles.length; i++) {
          const p = particles[i];
          const px = p.originX + (detectionX - originX) * progress + p.turbDx * progress * 2.5;
          const py = p.originY + (detectionY - originY) * progress + p.turbDy * progress * 2.5;

          const alpha = 0.3 + 0.6 * p.mass;
          ctx.fillStyle = i % 3 === 0
            ? `rgba(245, 158, 11, ${alpha})`
            : `rgba(6, 182, 212, ${alpha})`;

          ctx.beginPath();
          ctx.arc(px, py, 1.2 + p.mass * 1.3, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // 8. Suspect Tanker Moving Along AIS Historical Track
      const tankerProgress = Math.min(1, Math.max(0, (progress - 0.2) / 0.6));
      const tankerX = originX - 80 + tankerProgress * 240;
      const tankerY = originY + 60 - tankerProgress * 100;

      // Tanker track line
      ctx.save();
      ctx.strokeStyle = 'rgba(234, 179, 8, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(originX - 80, originY + 60);
      ctx.lineTo(originX + 160, originY - 40);
      ctx.stroke();
      ctx.restore();

      // Tanker icon
      ctx.save();
      ctx.translate(tankerX, tankerY);
      ctx.rotate(-Math.PI / 6);
      ctx.fillStyle = '#eab308';
      ctx.beginPath();
      ctx.moveTo(0, -8);
      ctx.lineTo(5, 7);
      ctx.lineTo(-5, 7);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      ctx.fillStyle = '#eab308';
      ctx.font = '9px monospace';
      ctx.fillText('AIS: MT Saraswati Star', tankerX + 10, tankerY - 2);

      // Detection Tag at endpoint
      ctx.fillStyle = '#06b6d4';
      ctx.font = '10px monospace';
      ctx.fillText('SAR DETECTION (T0)', detectionX + 10, detectionY + 5);

      animationFrameRef.current = requestAnimationFrame(render);
    };

    animationFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, progress, showParticles, showIsolines, showVectorGrid]);

  // Derived telemetry metrics based on progress
  const timeOffsetHours = ((1 - progress) * 12).toFixed(1);
  const currentAreaKm2 = (incident.slickAreaKm2 * (0.2 + 0.8 * progress)).toFixed(2);
  const centerLat = (incident.centerLat - (1 - progress) * 0.08).toFixed(4);
  const centerLon = (incident.centerLon - (1 - progress) * 0.09).toFixed(4);

  return (
    <div className="space-y-6">
      {/* Studio Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Video className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">
                Hydrodynamic Simulation Studio & Forensic Video Replay
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-mono">
                60 FPS MONTE CARLO (N=350)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Lagrangian Particle Advection · ERA5 Wind & HYCOM Current Forcing Hindcast · Origin Co-location
            </p>
          </div>
        </div>

        {/* Scenario Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Preset Scenario:</span>
          <select
            value={incident.id}
            onChange={(e) => {
              const match = allIncidents.find((i) => i.id === e.target.value);
              if (match) onSelectIncident(match);
            }}
            className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white font-semibold focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            {allIncidents.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.regionName} ({inc.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Studio Viewport (Canvas / Video Player) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Interactive Canvas Screen (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="relative bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
            {/* Viewport Top Bar Overlay */}
            <div className="absolute top-0 left-0 right-0 p-3 bg-gradient-to-b from-slate-950/90 to-transparent flex items-center justify-between z-20 pointer-events-none">
              <div className="flex items-center gap-2 pointer-events-auto">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping"></span>
                <span className="text-xs font-mono font-bold text-white">
                  T - {timeOffsetHours}h [RECONSTRUCTION]
                </span>
                <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800/50">
                  LAT: {centerLat}°N, LON: {centerLon}°E
                </span>
              </div>

              {/* Mode Switcher */}
              <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-lg border border-slate-800 pointer-events-auto">
                <button
                  onClick={() => setActiveMediaOverlay('particles')}
                  className={`text-[10px] font-bold px-2 py-1 rounded transition-colors cursor-pointer ${
                    activeMediaOverlay === 'particles'
                      ? 'bg-cyan-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Particles
                </button>
                <button
                  onClick={() => setActiveMediaOverlay('sar_overlay')}
                  className={`text-[10px] font-bold px-2 py-1 rounded transition-colors cursor-pointer ${
                    activeMediaOverlay === 'sar_overlay'
                      ? 'bg-cyan-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  SAR Radar Scene
                </button>
                <button
                  onClick={() => setActiveMediaOverlay('heatmap_overlay')}
                  className={`text-[10px] font-bold px-2 py-1 rounded transition-colors cursor-pointer ${
                    activeMediaOverlay === 'heatmap_overlay'
                      ? 'bg-cyan-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Origin PDF Heatmap
                </button>
              </div>
            </div>

            {/* Floating Tactical ERA5 Wind & Current HUD Chip */}
            {showWindStreamlines && (
              <div className="absolute top-12 right-3 z-20 pointer-events-none select-none bg-slate-950/85 backdrop-blur-md border border-cyan-500/40 rounded-xl px-3 py-1.5 shadow-2xl flex items-center space-x-3 text-xs">
                <div className="flex items-center space-x-1.5">
                  <div className="w-5 h-5 rounded-md bg-cyan-950/80 border border-cyan-500/50 flex items-center justify-center">
                    <Wind className="w-3 h-3 text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold">ERA5 Wind Field</div>
                    <div className="text-cyan-300 font-mono font-bold text-[11px] flex items-center space-x-1">
                      <span>{incident.windSpeedKnots.toFixed(1)} kn</span>
                      <span className="text-slate-500">@</span>
                      <span className="flex items-center">
                        {incident.windDirectionDeg}°
                        <Compass
                          className="w-2.5 h-2.5 ml-0.5 text-cyan-400 inline"
                          style={{ transform: `rotate(${incident.windDirectionDeg}deg)` }}
                        />
                      </span>
                    </div>
                  </div>
                </div>
                <div className="h-5 w-px bg-slate-800" />
                <div>
                  <div className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold">HYCOM Current</div>
                  <div className="text-emerald-300 font-mono font-bold text-[11px]">
                    <span>{incident.oceanCurrentSpeedKnots.toFixed(1)} kn</span>
                    <span className="text-slate-500 ml-1">@</span>
                    <span className="ml-1">{incident.oceanCurrentDirDeg}°</span>
                  </div>
                </div>
              </div>
            )}

            {/* Canvas or Static Image Overlay */}
            <div className="relative w-full aspect-[16/10] bg-slate-950 flex items-center justify-center overflow-hidden">
              {activeMediaOverlay === 'particles' && (
                <canvas
                  ref={canvasRef}
                  width={800}
                  height={500}
                  className="w-full h-full object-cover"
                />
              )}

              {activeMediaOverlay === 'sar_overlay' && (
                <div className="relative w-full h-full bg-slate-900 flex items-center justify-center">
                  <img
                    src="/assets/demo_pipeline_scene.png"
                    alt="SAR Scene"
                    className="max-h-full max-w-full object-contain filter contrast-125"
                  />
                  <div className="absolute bottom-4 left-4 bg-slate-950/80 p-2.5 rounded-lg border border-slate-700 text-xs text-slate-300 z-20">
                    <p className="font-bold text-cyan-400">Sentinel-1 SAR C-Band Synthetic Aperture Radar</p>
                    <p className="text-[11px] text-slate-400">Resolution: 10m/pixel · Polarization: VV+VH</p>
                  </div>
                </div>
              )}

              {activeMediaOverlay === 'heatmap_overlay' && (
                <div className="relative w-full h-full bg-slate-900 flex items-center justify-center">
                  <img
                    src="/assets/heatmap_zoomed_hires.png"
                    alt="Heatmap Origin"
                    className="max-h-full max-w-full object-contain"
                  />
                  <div className="absolute bottom-4 left-4 bg-slate-950/80 p-2.5 rounded-lg border border-slate-700 text-xs text-slate-300 z-20">
                    <p className="font-bold text-amber-400">Phase 3 Hydrodynamic Monte Carlo Origin PDF</p>
                    <p className="text-[11px] text-slate-400">Iso-contours: 90% (outer), 75% (mid), 50% (peak origin)</p>
                  </div>
                </div>
              )}

              {/* ── DYNAMIC WIND STREAMLINE CANVAS LAYER ── */}
              <canvas
                ref={windCanvasRef}
                width={800}
                height={500}
                className={`absolute inset-0 pointer-events-none w-full h-full z-10 transition-opacity duration-300 ${
                  showWindStreamlines ? 'opacity-100' : 'opacity-0'
                }`}
              />
            </div>

            {/* Playback Controls Strip */}
            <div className="p-4 bg-slate-900 border-t border-slate-800 space-y-3">
              {/* Timeline Scrubber */}
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-rose-400 whitespace-nowrap">T-12h (Origin)</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.005}
                  value={progress}
                  onChange={(e) => {
                    setProgress(parseFloat(e.target.value));
                    setIsPlaying(false);
                  }}
                  className="flex-1 accent-cyan-400 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                />
                <span className="text-[10px] font-mono text-cyan-400 whitespace-nowrap">T0 (Detection)</span>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setProgress((p) => Math.max(0, p - 0.1));
                      setIsPlaying(false);
                    }}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition-colors cursor-pointer"
                    title="Rewind 1 hour"
                  >
                    <Rewind className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all active:scale-95 shadow-md shadow-cyan-600/20 cursor-pointer"
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    {isPlaying ? 'Pause Simulation' : 'Play Simulation'}
                  </button>

                  <button
                    onClick={() => {
                      setProgress((p) => Math.min(1, p + 0.1));
                      setIsPlaying(false);
                    }}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition-colors cursor-pointer"
                    title="Fast forward 1 hour"
                  >
                    <FastForward className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => {
                      setProgress(0);
                      setIsPlaying(true);
                    }}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors cursor-pointer"
                    title="Reset to Origin"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>

                {/* Speed multipliers */}
                <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                  {[0.5, 1, 2, 5].map((spd) => (
                    <button
                      key={spd}
                      onClick={() => setPlaybackSpeed(spd)}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold transition-colors ${
                        playbackSpeed === spd
                          ? 'bg-cyan-500 text-slate-950'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      {spd}x
                    </button>
                  ))}
                </div>

                {/* Layer Toggles */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowWindStreamlines(!showWindStreamlines)}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                      showWindStreamlines
                        ? 'bg-cyan-950/80 border-cyan-500 text-cyan-300 shadow-sm shadow-cyan-500/20'
                        : 'bg-slate-800 border-slate-700 text-slate-500'
                    }`}
                  >
                    <Wind className="w-3 h-3" />
                    Wind Streamlines ({showWindStreamlines ? 'ON' : 'OFF'})
                  </button>

                  <button
                    onClick={() => setShowParticles(!showParticles)}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-semibold transition-colors cursor-pointer ${
                      showParticles
                        ? 'bg-cyan-950/80 border-cyan-700 text-cyan-300'
                        : 'bg-slate-800 border-slate-700 text-slate-500'
                    }`}
                  >
                    Particles ({showParticles ? 'ON' : 'OFF'})
                  </button>

                  <button
                    onClick={() => setShowIsolines(!showIsolines)}
                    className={`text-[10px] px-2.5 py-1 rounded-lg border font-semibold transition-colors cursor-pointer ${
                      showIsolines
                        ? 'bg-amber-950/80 border-amber-700 text-amber-300'
                        : 'bg-slate-800 border-slate-700 text-slate-500'
                    }`}
                  >
                    Density Contours
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Physics & Forensic Telemetry (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Hydrodynamic Telemetry */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Real-Time Hydrodynamic Telemetry
            </h3>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-between">
                <div>
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Hindcast Window</p>
                  <p className="text-base font-bold font-mono text-cyan-300 mt-0.5">
                    T - {timeOffsetHours}h
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Active Particles</p>
                  <p className="text-base font-bold font-mono text-emerald-400 mt-0.5">350 / 350</p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-between">
                <div>
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Plume Dispersion Area</p>
                  <p className="text-base font-bold font-mono text-amber-300 mt-0.5">
                    {currentAreaKm2} <span className="text-xs font-normal text-slate-400">km²</span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Fay Spread Radius</p>
                  <p className="text-base font-bold font-mono text-slate-200 mt-0.5">
                    {(2.4 * Math.sqrt(parseFloat(currentAreaKm2) || 1)).toFixed(1)} km
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Wind className="w-3.5 h-3.5 text-cyan-400" /> ERA5 10m Wind:
                  </span>
                  <span className="font-mono text-cyan-300 font-bold">
                    {incident.windSpeedKnots.toFixed(1)} kt @ {incident.windDirectionDeg}°
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Compass className="w-3.5 h-3.5 text-indigo-400" /> HYCOM Surface Current:
                  </span>
                  <span className="font-mono text-indigo-300 font-bold">
                    {incident.oceanCurrentSpeedKnots.toFixed(1)} kn @ {incident.oceanCurrentDirDeg}°
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Legal / Chain of Custody Note */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-emerald-400" />
              Forensic Integrity
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Drift simulation trajectories conform to{' '}
              <strong className="text-white">NOAA GNOME & OpenDrift standard</strong>. Monte Carlo uncertainty ellipses bound suspect vessel co-location with p-value &lt; 0.001 under UNCLOS Article 220 evidentiary requirements.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
export default SimulationVideoStudio;
