import React, { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import { Wind, Compass } from 'lucide-react';
import { IncidentCase } from '../App';

interface Props {
  incident: IncidentCase;
  visible?: boolean;
}

interface WindStreak {
  x: number;
  y: number;
  length: number;
  speed: number;
  alpha: number;
  width: number;
}

export const TacticalWindOverlay: React.FC<Props> = ({ incident, visible = true }) => {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streaksRef = useRef<WindStreak[]>([]);
  const animRef = useRef<number | null>(null);

  // Direction meteorology: windDirectionDeg is direction FROM which wind blows (0 = North, 90 = East)
  // Flow direction in screen coordinates (0 rad = +X right, PI/2 = +Y down):
  // North wind (0 deg) blows SOUTH (+Y).
  // Math: angleRad = ((incident.windDirectionDeg - 90 + 180) * Math.PI) / 180 = ((incident.windDirectionDeg + 90) * Math.PI) / 180
  const windAngleRad = ((incident.windDirectionDeg + 90) * Math.PI) / 180;
  const currentAngleRad = ((incident.oceanCurrentDirDeg + 90) * Math.PI) / 180;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const size = map.getSize();
      canvas.width = size.x;
      canvas.height = size.y;
    };
    resize();

    // Initialize 60 wind streamline particles
    const list: WindStreak[] = [];
    const count = 55;
    for (let i = 0; i < count; i++) {
      list.push({
        x: Math.random() * (canvas.width || 800),
        y: Math.random() * (canvas.height || 600),
        length: 22 + Math.random() * 26,
        speed: (incident.windSpeedKnots * 0.12 + 0.8) * (0.8 + Math.random() * 0.4),
        alpha: 0.15 + Math.random() * 0.35,
        width: 1.2 + Math.random() * 1.4,
      });
    }
    streaksRef.current = list;

    map.on('resize', resize);
    map.on('move', resize);

    return () => {
      map.off('resize', resize);
      map.off('move', resize);
    };
  }, [map, incident.windSpeedKnots, incident.windDirectionDeg]);

  // Render loop
  useEffect(() => {
    if (!visible) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dx = Math.cos(windAngleRad);
    const dy = Math.sin(windAngleRad);

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const streaks = streaksRef.current;

      for (let i = 0; i < streaks.length; i++) {
        const s = streaks[i];

        // Move streak
        s.x += dx * s.speed;
        s.y += dy * s.speed;

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
          const a1X = s.x - arrowLen * Math.cos(windAngleRad - arrowAngle);
          const a1Y = s.y - arrowLen * Math.sin(windAngleRad - arrowAngle);
          const a2X = s.x - arrowLen * Math.cos(windAngleRad + arrowAngle);
          const a2Y = s.y - arrowLen * Math.sin(windAngleRad + arrowAngle);

          ctx.fillStyle = `rgba(165, 243, 252, ${s.alpha * 0.9})`;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(a1X, a1Y);
          ctx.lineTo(a2X, a2Y);
          ctx.closePath();
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [visible, windAngleRad, incident.windSpeedKnots]);

  if (!visible) return null;

  return (
    <>
      {/* 60fps Vector Streamlines Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none z-[450] w-full h-full"
      />

      {/* Floating Tactical Environmental HUD Chip on Map */}
      <div className="absolute top-4 right-4 z-[1000] pointer-events-auto bg-slate-950/85 backdrop-blur-md border border-cyan-500/40 rounded-xl p-3 shadow-2xl space-y-1.5 min-w-[210px]">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
          <div className="flex items-center gap-1.5 text-cyan-400 text-[11px] font-bold tracking-wider uppercase font-mono">
            <Wind className="w-3.5 h-3.5 animate-pulse" />
            <span>ERA5 Wind Field</span>
          </div>
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400 font-mono">Velocity:</span>
          <span className="text-cyan-300 font-mono font-bold">
            {incident.windSpeedKnots.toFixed(1)} kn ({incident.windDirectionDeg}°)
          </span>
        </div>

        <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/60">
          <div className="flex items-center gap-1 text-slate-400 text-[11px] font-mono">
            <Compass className="w-3 h-3 text-indigo-400" />
            <span>Current:</span>
          </div>
          <span className="text-indigo-300 font-mono font-bold text-xs">
            {incident.oceanCurrentSpeedKnots.toFixed(1)} kn @ {incident.oceanCurrentDirDeg}°
          </span>
        </div>
      </div>
    </>
  );
};
export default TacticalWindOverlay;
