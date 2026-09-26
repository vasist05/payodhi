import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  MapContainer, TileLayer, Polygon, Polyline, Circle, Marker, Popup, Tooltip, useMap,
} from 'react-leaflet';
import L from 'leaflet';
import {
  Shield, FileText, Satellite, Zap, RefreshCw, Radio, Wind, Compass,
  Droplet, Clock, CheckCircle2, Check, Ship, AlertTriangle,
  XCircle, HelpCircle, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Award, FileCheck,
  Navigation, Layers, Bot, Send, User, Radar, Sun, Moon, Database,
  Play, Pause, RotateCcw, FastForward, Rewind, History, Upload, MapPin,
  Loader2, X, Printer, Activity, BarChart3, LayoutDashboard, Sparkles,
  Search, Filter, Eye, EyeOff, Maximize2, Minimize2, Terminal, Waves, Anchor, Info,
  Video,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip as RechartTooltip, ResponsiveContainer,
  AreaChart, Area, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar as RechartRadar,
} from 'recharts';
import { CoastGuardAlertPanel } from './components/CoastGuardAlertPanel';
import { SimulationVideoStudio } from './components/SimulationVideoStudio';
import { TacticalWindOverlay } from './components/TacticalWindOverlay';
import { useResponses } from './hooks/useResponses';


// ============================================================
// TYPES
// ============================================================
export type LatLng = [number, number];

export interface TrackPoint {
  lat: number; lon: number; timestamp: string;
  sogKnots: number; cogDegrees: number;
}

export interface SuspectVessel {
  id: string; mmsi: string; name: string; type: string; flag: string;
  lengthMeters: number; grossTonnage: number; lastCargo: string;
  isDarkVessel: boolean;
  attributionScore: number;
  evidenceGrade: 'STRONG' | 'INCONCLUSIVE' | 'LOW';
  driftAgreement: number; timeOverlap: number; spatialProximity: number;
  vesselCharacteristics: number; behavioralAnomaly: number;
  distanceToOriginKm: number; timeDiffMinutes: number;
  keyEvidence: string[]; disqualificationReasons: string[];
  track: TrackPoint[];
}

export interface OriginHeatmapPoint {
  lat: number; lon: number; probability: number; radiusMeters: number;
}

export interface DriftTrajectoryPoint {
  hoursFromDetection: number; lat: number; lon: number;
  timestamp: string; uncertaintyRadiusKm: number;
}

export interface IncidentCase {
  id: string; title: string; regionName: string; incidentDate: string;
  detectionTimestamp: string;
  estimatedReleaseWindow: { start: string; end: string; hoursBeforeDetection: number };
  centerLat: number; centerLon: number; zoomLevel: number;
  slickPolygon: LatLng[]; slickAreaKm2: number; slickPerimeterKm: number;
  estimatedVolumeBarrels: number; estimatedAgeHours: number;
  fpFilterConfidence: number; isVerifiedOil: boolean; lookalikeCategoryChecked: string;
  windU10: number; windV10: number; windSpeedKnots: number; windDirectionDeg: number;
  oceanCurrentSpeedKnots: number; oceanCurrentDirDeg: number;
  seaSurfaceTempC: number; waveHeightM: number;
  backwardDriftPath: DriftTrajectoryPoint[];
  forwardDriftForecast: DriftTrajectoryPoint[];
  originHeatmap: OriginHeatmapPoint[];
  suspects: SuspectVessel[];
  summaryNotes: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
}

export type TabKey =
  | 'dashboard'
  | 'map'
  | 'simulation-video'
  | 'attribution'
  | 'cg-alerts'
  | 'ai'
  | 'analytics'
  | 'reports'
  | 'ingest';

// ============================================================
// DEMO MODE STATE
// ============================================================
interface DemoPhaseStatus {
  name: string;
  sub: string;
  timing: string;
  done: boolean;
  active: boolean;
}

const DEMO_PIPELINE_PHASES: Omit<DemoPhaseStatus, 'done' | 'active'>[] = [
  { name: 'SAR Segmentation (U-Net)', sub: 'Sentinel-1A C-Band · 10m Resolution', timing: '342ms' },
  { name: 'False-Positive Filter (CNN)', sub: 'Algal Bloom & Wind Shadow Rejection', timing: '128ms' },
  { name: 'Drift Hindcast — Backward', sub: 'Eulerian Advection · ECMWF / INCOIS Physics', timing: '891ms' },
  { name: 'AIS Correlation & Dark Vessel', sub: 'Spatio-Temporal Intersect & Radar Matching', timing: '203ms' },
  { name: 'Multi-Factor Attribution', sub: 'Bayesian Weighting · 5 Core Dimensions', timing: '156ms' },
  { name: 'Evidence Dossier Generation', sub: 'NTRO & Coast Guard Compliance Ready', timing: '74ms' },
];

interface LogEvent {
  time: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

const PRESET_SECTORS = [
  { label: 'Ennore / Kamarajar Port, Chennai', lat: 13.23, lon: 80.33, dLon: 0.03, zoom: 11 },
  { label: 'Visakhapatnam Outer Anchorage',    lat: 17.68, lon: 83.28, dLon: 0.04, zoom: 11 },
  { label: 'Paradip Port, Odisha',             lat: 20.26, lon: 86.65, dLon: 0.03, zoom: 11 },
  { label: 'Mumbai High Offshore Field',       lat: 19.20, lon: 71.50, dLon: -0.03, zoom: 11 },
  { label: 'Cochin (Kochi) Outer Roadstead',   lat: 9.94,  lon: 76.24, dLon: -0.03, zoom: 11 },
];

// ============================================================
// DEMO INCIDENT — MV Saraswati Star (2024-03-15, Kamarajar Port)
// ============================================================
const DEMO_INCIDENT: IncidentCase = {
  id: 'demo-live-2024',
  title: 'LIVE — MV Saraswati Star Oil Release',
  regionName: 'Outer Shipping Corridor · Bay of Bengal (12nm Offshore)',
  incidentDate: '2024-03-15',
  detectionTimestamp: '2024-03-15T06:42:00Z',
  estimatedReleaseWindow: {
    start: '2024-03-15T01:12:00Z',
    end: '2024-03-15T02:30:00Z',
    hoursBeforeDetection: 5.5,
  },
  centerLat: 13.33, centerLon: 80.46, zoomLevel: 12,
  slickPolygon: [
    [13.413, 80.467],
    [13.394, 80.453],
    [13.377, 80.437],
    [13.346, 80.425],
    [13.316, 80.415],
    [13.292, 80.424],
    [13.278, 80.436],
    [13.278, 80.446],
    [13.286, 80.451],
    [13.307, 80.468],
    [13.322, 80.472],
    [13.327, 80.487],
    [13.343, 80.504],
    [13.357, 80.523],
  ],
  slickAreaKm2: 86.4, slickPerimeterKm: 42.6,
  estimatedVolumeBarrels: 1250, estimatedAgeHours: 5.5,
  fpFilterConfidence: 0.943, isVerifiedOil: true,
  lookalikeCategoryChecked: 'Algal Bloom & Low Wind Shadow',
  windU10: -2.8, windV10: -3.6, windSpeedKnots: 8.6, windDirectionDeg: 35,
  oceanCurrentSpeedKnots: 0.9, oceanCurrentDirDeg: 185,
  seaSurfaceTempC: 28.4, waveHeightM: 1.2,
  backwardDriftPath: [
    { hoursFromDetection: 0,    lat: 13.275, lon: 80.470, timestamp: '2024-03-15T06:42:00Z', uncertaintyRadiusKm: 0.7 },
    { hoursFromDetection: -1.5, lat: 13.292, lon: 80.465, timestamp: '2024-03-15T05:12:00Z', uncertaintyRadiusKm: 1.4 },
    { hoursFromDetection: -3.0, lat: 13.308, lon: 80.460, timestamp: '2024-03-15T03:42:00Z', uncertaintyRadiusKm: 2.1 },
    { hoursFromDetection: -5.0, lat: 13.328, lon: 80.454, timestamp: '2024-03-15T01:42:00Z', uncertaintyRadiusKm: 3.0 },
    { hoursFromDetection: -5.5, lat: 13.340, lon: 80.450, timestamp: '2024-03-15T01:12:00Z', uncertaintyRadiusKm: 3.5 },
  ],
  forwardDriftForecast: [
    { hoursFromDetection: 0,    lat: 13.275, lon: 80.470, timestamp: '2024-03-15T06:42:00Z', uncertaintyRadiusKm: 0.7 },
    { hoursFromDetection: 6.0,  lat: 13.230, lon: 80.475, timestamp: '2024-03-15T12:42:00Z', uncertaintyRadiusKm: 2.6 },
    { hoursFromDetection: 12.0, lat: 13.185, lon: 80.480, timestamp: '2024-03-15T18:42:00Z', uncertaintyRadiusKm: 4.8 },
    { hoursFromDetection: 24.0, lat: 13.090, lon: 80.490, timestamp: '2024-03-16T06:42:00Z', uncertaintyRadiusKm: 8.3 },
  ],
  originHeatmap: [
    { lat: 13.340, lon: 80.450, probability: 0.96, radiusMeters: 1400 },
    { lat: 13.332, lon: 80.455, probability: 0.78, radiusMeters: 2200 },
    { lat: 13.348, lon: 80.445, probability: 0.54, radiusMeters: 3100 },
  ],
  suspects: [
    {
      id: 'demo-vessel-primary',
      mmsi: '419118843',
      name: 'MV Saraswati Star',
      type: 'Crude Oil Tanker',
      flag: 'India (IN)',
      lengthMeters: 228,
      grossTonnage: 48000,
      lastCargo: 'Arabian Crude (Grade A)',
      isDarkVessel: false,
      attributionScore: 93,
      evidenceGrade: 'STRONG',
      driftAgreement: 96, timeOverlap: 94, spatialProximity: 91,
      vesselCharacteristics: 90, behavioralAnomaly: 88,
      distanceToOriginKm: 0.4, timeDiffMinutes: 6,
      keyEvidence: [
        'Sudden course deviation at 01:15 UTC — 22° starboard turn recorded',
        'AIS signal gap of 43 minutes (01:18–02:01 UTC) near origin centroid',
        'Vessel draft records indicate ballast tank venting consistent with oil discharge',
        'Backward drift physics 96% match — origin centroid within 400m of vessel track',
      ],
      disqualificationReasons: [],
      track: [
        { lat: 13.385, lon: 80.495, timestamp: '2024-03-15T00:00:00Z', sogKnots: 11.2, cogDegrees: 215 },
        { lat: 13.365, lon: 80.475, timestamp: '2024-03-15T00:45:00Z', sogKnots: 10.4, cogDegrees: 212 },
        { lat: 13.342, lon: 80.452, timestamp: '2024-03-15T01:15:00Z', sogKnots: 2.1,  cogDegrees: 190 },
        { lat: 13.330, lon: 80.446, timestamp: '2024-03-15T02:05:00Z', sogKnots: 0.8,  cogDegrees: 185 },
        { lat: 13.315, lon: 80.442, timestamp: '2024-03-15T03:30:00Z', sogKnots: 0.4,  cogDegrees: 180 },
        { lat: 13.295, lon: 80.439, timestamp: '2024-03-15T05:00:00Z', sogKnots: 0.2,  cogDegrees: 178 },
        { lat: 13.280, lon: 80.436, timestamp: '2024-03-15T06:42:00Z', sogKnots: 0.1,  cogDegrees: 178 },
      ],
    },
    {
      id: 'demo-vessel-dark',
      mmsi: 'DARK-TGT-014',
      name: 'Unidentified Radar Contact',
      type: 'Suspected Coaster (RCS ~70m)',
      flag: 'Unknown (No AIS)',
      lengthMeters: 70, grossTonnage: 1900, lastCargo: 'Unknown',
      isDarkVessel: true, attributionScore: 44, evidenceGrade: 'INCONCLUSIVE',
      driftAgreement: 52, timeOverlap: 55, spatialProximity: 47,
      vesselCharacteristics: 28, behavioralAnomaly: 82,
      distanceToOriginKm: 5.2, timeDiffMinutes: 72,
      keyEvidence: ['High-intensity SAR return, no transponder signal', 'Stationary contact near shipping lane perimeter'],
      disqualificationReasons: ['No historical trajectory — radar-only contact', 'Distance from origin centroid exceeds 5 km threshold'],
      track: [
        { lat: 13.350, lon: 80.520, timestamp: '2024-03-15T00:00:00Z', sogKnots: 1.8, cogDegrees: 160 },
        { lat: 13.355, lon: 80.523, timestamp: '2024-03-15T06:42:00Z', sogKnots: 1.2, cogDegrees: 165 },
      ],
    },
    {
      id: 'demo-vessel-cleared',
      mmsi: '419078222',
      name: 'MV Kalavathi',
      type: 'LPG Carrier',
      flag: 'India (IN)',
      lengthMeters: 180, grossTonnage: 22000, lastCargo: 'Liquid Propane Gas',
      isDarkVessel: false, attributionScore: 21, evidenceGrade: 'LOW',
      driftAgreement: 62, timeOverlap: 58, spatialProximity: 60,
      vesselCharacteristics: 5, behavioralAnomaly: 25,
      distanceToOriginKm: 2.8, timeDiffMinutes: 38,
      keyEvidence: ['Transited within 2.8 km of origin during release window'],
      disqualificationReasons: [
        'Non-persistent cryogenic LPG cargo — cannot form visible oil slick',
        'Hull penetration limited to forward void space, confirmed by port inspection',
      ],
      track: [
        { lat: 13.240, lon: 80.420, timestamp: '2024-03-15T00:30:00Z', sogKnots: 11.2, cogDegrees: 40 },
        { lat: 13.310, lon: 80.438, timestamp: '2024-03-15T01:30:00Z', sogKnots: 10.8, cogDegrees: 42 },
        { lat: 13.375, lon: 80.455, timestamp: '2024-03-15T02:30:00Z', sogKnots: 11.0, cogDegrees: 40 },
      ],
    },
  ],
  summaryNotes: 'Demo scenario: MV Saraswati Star identified as primary source with 93/100 attribution confidence.',
  severity: 'CRITICAL',
};

const INCIDENT_CASES: IncidentCase[] = [
  DEMO_INCIDENT,
  {
    id: 'chennai-2017',
    title: 'Chennai / Ennore Tanker Collision (2017)',
    regionName: 'Ennore Outer Fairway · Bay of Bengal (10nm Offshore)',
    incidentDate: '2017-01-28',
    detectionTimestamp: '2017-01-28T12:00:00Z',
    estimatedReleaseWindow: {
      start: '2017-01-28T04:00:00Z', end: '2017-01-28T05:30:00Z',
      hoursBeforeDetection: 7.5,
    },
    centerLat: 13.325, centerLon: 80.435, zoomLevel: 12,
    slickPolygon: [
      [13.350, 80.420], [13.335, 80.445], [13.305, 80.450],
      [13.285, 80.435], [13.300, 80.415], [13.330, 80.410],
    ],
    slickAreaKm2: 34.2, slickPerimeterKm: 28.6,
    estimatedVolumeBarrels: 1850, estimatedAgeHours: 7.8,
    fpFilterConfidence: 0.968, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Algal Bloom & Coastal Wave Shadow',
    windU10: -3.5, windV10: -4.2, windSpeedKnots: 10.6, windDirectionDeg: 40,
    oceanCurrentSpeedKnots: 1.1, oceanCurrentDirDeg: 195,
    seaSurfaceTempC: 27.2, waveHeightM: 1.5,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 13.290, lon: 80.425, timestamp: '2017-01-28T12:00:00Z', uncertaintyRadiusKm: 0.8 },
      { hoursFromDetection: -2.0, lat: 13.305, lon: 80.420, timestamp: '2017-01-28T10:00:00Z', uncertaintyRadiusKm: 1.5 },
      { hoursFromDetection: -4.0, lat: 13.320, lon: 80.416, timestamp: '2017-01-28T08:00:00Z', uncertaintyRadiusKm: 2.2 },
      { hoursFromDetection: -6.0, lat: 13.335, lon: 80.412, timestamp: '2017-01-28T06:00:00Z', uncertaintyRadiusKm: 2.9 },
      { hoursFromDetection: -7.5, lat: 13.345, lon: 80.410, timestamp: '2017-01-28T04:30:00Z', uncertaintyRadiusKm: 3.5 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 13.290, lon: 80.425, timestamp: '2017-01-28T12:00:00Z', uncertaintyRadiusKm: 0.8 },
      { hoursFromDetection: 6.0, lat: 13.260, lon: 80.430, timestamp: '2017-01-28T18:00:00Z', uncertaintyRadiusKm: 2.8 },
      { hoursFromDetection: 12.0, lat: 13.220, lon: 80.435, timestamp: '2017-01-29T00:00:00Z', uncertaintyRadiusKm: 4.9 },
      { hoursFromDetection: 24.0, lat: 13.150, lon: 80.440, timestamp: '2017-01-29T12:00:00Z', uncertaintyRadiusKm: 8.5 },
    ],
    originHeatmap: [
      { lat: 13.345, lon: 80.410, probability: 0.98, radiusMeters: 1600 },
      { lat: 13.338, lon: 80.415, probability: 0.82, radiusMeters: 2400 },
      { lat: 13.352, lon: 80.408, probability: 0.68, radiusMeters: 3100 },
    ],
    suspects: [
      {
        id: 'vessel-chennai-1', mmsi: '419000840', name: 'MT Dawn Kanchipuram',
        type: 'Petroleum Products Tanker', flag: 'India (IN)',
        lengthMeters: 183, grossTonnage: 29800, lastCargo: 'Heavy Bunker Fuel',
        isDarkVessel: false, attributionScore: 96, evidenceGrade: 'STRONG',
        driftAgreement: 98, timeOverlap: 96, spatialProximity: 98,
        vesselCharacteristics: 95, behavioralAnomaly: 92,
        distanceToOriginKm: 0.3, timeDiffMinutes: 5,
        keyEvidence: [
          'Exact co-location with collision epicenter at 04:32 UTC',
          'Sudden trajectory halt and post-impact course divergence',
          'Heavy bunker fuel cargo breach documented in casualty filings',
          'Southward drift correlates 98% with coastal contamination',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 13.385, lon: 80.445, timestamp: '2017-01-28T03:30:00Z', sogKnots: 11.2, cogDegrees: 210 },
          { lat: 13.356, lon: 80.421, timestamp: '2017-01-28T04:30:00Z', sogKnots: 2.1, cogDegrees: 140 },
          { lat: 13.350, lon: 80.423, timestamp: '2017-01-28T06:00:00Z', sogKnots: 0.4, cogDegrees: 190 },
          { lat: 13.345, lon: 80.425, timestamp: '2017-01-28T09:00:00Z', sogKnots: 0.2, cogDegrees: 180 },
          { lat: 13.340, lon: 80.427, timestamp: '2017-01-28T12:00:00Z', sogKnots: 0.1, cogDegrees: 180 },
        ],
      },
      {
        id: 'vessel-chennai-2', mmsi: '235086000', name: 'BW Maple',
        type: 'LPG Carrier', flag: 'Isle of Man (GB)',
        lengthMeters: 226, grossTonnage: 48000, lastCargo: 'Liquid Propane Gas',
        isDarkVessel: false, attributionScore: 68, evidenceGrade: 'INCONCLUSIVE',
        driftAgreement: 95, timeOverlap: 95, spatialProximity: 96,
        vesselCharacteristics: 15, behavioralAnomaly: 90,
        distanceToOriginKm: 0.4, timeDiffMinutes: 5,
        keyEvidence: ['Involved in the identical collision event at 04:32 UTC'],
        disqualificationReasons: [
          'Non-persistent cryogenic gas cargo (LPG), not persistent crude',
          'Hull penetration restricted to forward ballast tank',
        ],
        track: [
          { lat: 13.325, lon: 80.405, timestamp: '2017-01-28T03:30:00Z', sogKnots: 9.8, cogDegrees: 35 },
          { lat: 13.354, lon: 80.420, timestamp: '2017-01-28T04:30:00Z', sogKnots: 1.5, cogDegrees: 80 },
          { lat: 13.358, lon: 80.435, timestamp: '2017-01-28T06:00:00Z', sogKnots: 0.3, cogDegrees: 90 },
          { lat: 13.360, lon: 80.440, timestamp: '2017-01-28T12:00:00Z', sogKnots: 0.1, cogDegrees: 90 },
        ],
      },
      {
        id: 'vessel-chennai-dark', mmsi: 'DARK-TGT-092',
        name: 'Unidentified Radar Target',
        type: 'Suspected Coaster (RCS: 85m)', flag: 'Unknown (No AIS)',
        lengthMeters: 85, grossTonnage: 2800, lastCargo: 'Unknown',
        isDarkVessel: true, attributionScore: 62, evidenceGrade: 'INCONCLUSIVE',
        driftAgreement: 72, timeOverlap: 80, spatialProximity: 68,
        vesselCharacteristics: 50, behavioralAnomaly: 95,
        distanceToOriginKm: 3.4, timeDiffMinutes: 40,
        keyEvidence: [
          'High-intensity SAR return without AIS signal',
          'Stationary return near outer anchorage during release',
        ],
        disqualificationReasons: ['No historical trajectory (no transponder)'],
        track: [
          { lat: 13.370, lon: 80.475, timestamp: '2017-01-28T03:30:00Z', sogKnots: 1.8, cogDegrees: 180 },
          { lat: 13.355, lon: 80.478, timestamp: '2017-01-28T12:00:00Z', sogKnots: 1.5, cogDegrees: 175 },
        ],
      },
    ],
    summaryNotes: 'Clear attribution identifying MT Dawn Kanchipuram as the primary source.',
    severity: 'CRITICAL',
  },
  {
    id: 'mumbai-2023',
    title: 'Mumbai High Offshore Incident',
    regionName: 'Offshore Arabian Sea (EEZ Zone · 160km West)',
    incidentDate: '2023-11-05',
    detectionTimestamp: '2023-11-05T08:15:00Z',
    estimatedReleaseWindow: {
      start: '2023-11-05T03:00:00Z', end: '2023-11-05T04:45:00Z',
      hoursBeforeDetection: 4.5,
    },
    centerLat: 19.380, centerLon: 71.420, zoomLevel: 11,
    slickPolygon: [
      [19.410, 71.390], [19.395, 71.445], [19.360, 71.450],
      [19.345, 71.410], [19.370, 71.380],
    ],
    slickAreaKm2: 24.8, slickPerimeterKm: 22.4,
    estimatedVolumeBarrels: 620, estimatedAgeHours: 4.8,
    fpFilterConfidence: 0.915, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Low Wind Shadow near Offshore Rig',
    windU10: -2.1, windV10: 5.6, windSpeedKnots: 11.8, windDirectionDeg: 155,
    oceanCurrentSpeedKnots: 0.8, oceanCurrentDirDeg: 330,
    seaSurfaceTempC: 29.1, waveHeightM: 1.0,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 19.380, lon: 71.420, timestamp: '2023-11-05T08:15:00Z', uncertaintyRadiusKm: 0.6 },
      { hoursFromDetection: -1.5, lat: 19.362, lon: 71.432, timestamp: '2023-11-05T06:45:00Z', uncertaintyRadiusKm: 1.4 },
      { hoursFromDetection: -3.0, lat: 19.340, lon: 71.448, timestamp: '2023-11-05T05:15:00Z', uncertaintyRadiusKm: 2.1 },
      { hoursFromDetection: -4.5, lat: 19.318, lon: 71.465, timestamp: '2023-11-05T03:45:00Z', uncertaintyRadiusKm: 3.0 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 19.380, lon: 71.420, timestamp: '2023-11-05T08:15:00Z', uncertaintyRadiusKm: 0.6 },
      { hoursFromDetection: 6.0, lat: 19.418, lon: 71.395, timestamp: '2023-11-05T14:15:00Z', uncertaintyRadiusKm: 2.5 },
      { hoursFromDetection: 12.0, lat: 19.455, lon: 71.370, timestamp: '2023-11-05T20:15:00Z', uncertaintyRadiusKm: 5.1 },
      { hoursFromDetection: 24.0, lat: 19.525, lon: 71.320, timestamp: '2023-11-06T08:15:00Z', uncertaintyRadiusKm: 9.2 },
    ],
    originHeatmap: [
      { lat: 19.318, lon: 71.465, probability: 0.92, radiusMeters: 1800 },
      { lat: 19.328, lon: 71.455, probability: 0.74, radiusMeters: 2600 },
    ],
    suspects: [
      {
        id: 'vessel-mumbai-1', mmsi: '636019800', name: 'MT Gulf Trader',
        type: 'Crude Oil Tanker', flag: 'Liberia (LR)',
        lengthMeters: 244, grossTonnage: 56000, lastCargo: 'Arabian Light Crude',
        isDarkVessel: false, attributionScore: 84, evidenceGrade: 'STRONG',
        driftAgreement: 88, timeOverlap: 85, spatialProximity: 82,
        vesselCharacteristics: 92, behavioralAnomaly: 68,
        distanceToOriginKm: 1.8, timeDiffMinutes: 22,
        keyEvidence: [
          'Crossed within 1.8 km of origin centroid at 04:02 UTC',
          'Vessel draft records indicate high likelihood of bilge discharge',
          'Drift physics agreement confirms backward trajectory intersection',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 19.260, lon: 71.510, timestamp: '2023-11-05T02:00:00Z', sogKnots: 13.8, cogDegrees: 310 },
          { lat: 19.310, lon: 71.472, timestamp: '2023-11-05T03:45:00Z', sogKnots: 11.2, cogDegrees: 308 },
          { lat: 19.365, lon: 71.430, timestamp: '2023-11-05T05:30:00Z', sogKnots: 13.5, cogDegrees: 305 },
          { lat: 19.420, lon: 71.390, timestamp: '2023-11-05T07:15:00Z', sogKnots: 13.6, cogDegrees: 305 },
        ],
      },
    ],
    summaryNotes: 'Offshore illegal discharge candidate identified with 84/100 evidentiary support.',
    severity: 'HIGH',
  },
  {
    id: 'haldia-2018',
    title: 'Haldia / Sandheads SSL Kolkata Spill',
    regionName: 'Sandheads Fairway · Bay of Bengal (35nm Offshore)',
    incidentDate: '2018-07-14',
    detectionTimestamp: '2018-07-14T09:30:00Z',
    estimatedReleaseWindow: {
      start: '2018-07-14T02:00:00Z', end: '2018-07-14T04:30:00Z',
      hoursBeforeDetection: 6.0,
    },
    centerLat: 21.480, centerLon: 88.240, zoomLevel: 11,
    slickPolygon: [
      [21.510, 88.220], [21.495, 88.265], [21.460, 88.270],
      [21.445, 88.230], [21.470, 88.200],
    ],
    slickAreaKm2: 28.5, slickPerimeterKm: 24.2,
    estimatedVolumeBarrels: 890, estimatedAgeHours: 6.5,
    fpFilterConfidence: 0.932, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Monsoon Estuary Sediment Plume',
    windU10: -4.2, windV10: 2.8, windSpeedKnots: 12.4, windDirectionDeg: 120,
    oceanCurrentSpeedKnots: 1.4, oceanCurrentDirDeg: 25,
    seaSurfaceTempC: 28.6, waveHeightM: 1.8,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 21.480, lon: 88.240, timestamp: '2018-07-14T09:30:00Z', uncertaintyRadiusKm: 0.8 },
      { hoursFromDetection: -2.0, lat: 21.455, lon: 88.232, timestamp: '2018-07-14T07:30:00Z', uncertaintyRadiusKm: 1.6 },
      { hoursFromDetection: -4.0, lat: 21.430, lon: 88.224, timestamp: '2018-07-14T05:30:00Z', uncertaintyRadiusKm: 2.4 },
      { hoursFromDetection: -6.0, lat: 21.405, lon: 88.216, timestamp: '2018-07-14T03:30:00Z', uncertaintyRadiusKm: 3.2 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 21.480, lon: 88.240, timestamp: '2018-07-14T09:30:00Z', uncertaintyRadiusKm: 0.8 },
      { hoursFromDetection: 6.0, lat: 21.530, lon: 88.255, timestamp: '2018-07-14T15:30:00Z', uncertaintyRadiusKm: 2.7 },
      { hoursFromDetection: 12.0, lat: 21.580, lon: 88.270, timestamp: '2018-07-14T21:30:00Z', uncertaintyRadiusKm: 5.2 },
      { hoursFromDetection: 24.0, lat: 21.680, lon: 88.300, timestamp: '2018-07-15T09:30:00Z', uncertaintyRadiusKm: 8.9 },
    ],
    originHeatmap: [
      { lat: 21.405, lon: 88.216, probability: 0.94, radiusMeters: 1500 },
      { lat: 21.415, lon: 88.225, probability: 0.76, radiusMeters: 2300 },
    ],
    suspects: [
      {
        id: 'vessel-haldia-1', mmsi: '419001150', name: 'SSL Kolkata',
        type: 'Container Ship', flag: 'India (IN)',
        lengthMeters: 148, grossTonnage: 9956, lastCargo: 'Container Cargo & Heavy IFO-380',
        isDarkVessel: false, attributionScore: 91, evidenceGrade: 'STRONG',
        driftAgreement: 94, timeOverlap: 92, spatialProximity: 89,
        vesselCharacteristics: 86, behavioralAnomaly: 93,
        distanceToOriginKm: 0.6, timeDiffMinutes: 12,
        keyEvidence: [
          'Vessel reported onboard casualty and abandoned ship at 03:45 UTC',
          'Heavy bunker fuel slick detected along drift axis towards Sandheads',
          'Hydrodynamic hindcast correlates 94% with vessel drift trajectory',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 21.380, lon: 88.205, timestamp: '2018-07-14T01:30:00Z', sogKnots: 8.5, cogDegrees: 30 },
          { lat: 21.408, lon: 88.218, timestamp: '2018-07-14T03:30:00Z', sogKnots: 1.2, cogDegrees: 25 },
          { lat: 21.445, lon: 88.230, timestamp: '2018-07-14T06:00:00Z', sogKnots: 0.8, cogDegrees: 20 },
          { lat: 21.480, lon: 88.242, timestamp: '2018-07-14T09:30:00Z', sogKnots: 0.3, cogDegrees: 15 },
        ],
      },
    ],
    summaryNotes: 'Maritime accident verified with high-confidence oil slick drift attribution.',
    severity: 'HIGH',
  },
  {
    id: 'kochi-2025',
    title: 'Kochi Outer Roadstead Incident',
    regionName: 'International Tanker Highway · Arabian Sea (35km Offshore)',
    incidentDate: '2025-05-26',
    detectionTimestamp: '2025-05-26T11:00:00Z',
    estimatedReleaseWindow: {
      start: '2025-05-26T05:00:00Z', end: '2025-05-26T07:15:00Z',
      hoursBeforeDetection: 5.0,
    },
    centerLat: 9.920, centerLon: 75.820, zoomLevel: 11,
    slickPolygon: [
      [9.950, 75.800], [9.940, 75.845], [9.910, 75.850],
      [9.890, 75.810], [9.920, 75.790],
    ],
    slickAreaKm2: 21.4, slickPerimeterKm: 19.8,
    estimatedVolumeBarrels: 540, estimatedAgeHours: 5.2,
    fpFilterConfidence: 0.926, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Biogenic Ocean Film Rejection',
    windU10: 3.1, windV10: 4.8, windSpeedKnots: 11.2, windDirectionDeg: 215,
    oceanCurrentSpeedKnots: 1.2, oceanCurrentDirDeg: 345,
    seaSurfaceTempC: 29.4, waveHeightM: 1.3,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 9.920, lon: 75.820, timestamp: '2025-05-26T11:00:00Z', uncertaintyRadiusKm: 0.7 },
      { hoursFromDetection: -2.0, lat: 9.895, lon: 75.835, timestamp: '2025-05-26T09:00:00Z', uncertaintyRadiusKm: 1.5 },
      { hoursFromDetection: -5.0, lat: 9.855, lon: 75.860, timestamp: '2025-05-26T06:00:00Z', uncertaintyRadiusKm: 2.8 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 9.920, lon: 75.820, timestamp: '2025-05-26T11:00:00Z', uncertaintyRadiusKm: 0.7 },
      { hoursFromDetection: 6.0, lat: 9.965, lon: 75.800, timestamp: '2025-05-26T17:00:00Z', uncertaintyRadiusKm: 2.5 },
      { hoursFromDetection: 12.0, lat: 10.015, lon: 75.775, timestamp: '2025-05-26T23:00:00Z', uncertaintyRadiusKm: 4.8 },
      { hoursFromDetection: 24.0, lat: 10.110, lon: 75.725, timestamp: '2025-05-27T11:00:00Z', uncertaintyRadiusKm: 8.6 },
    ],
    originHeatmap: [
      { lat: 9.855, lon: 75.860, probability: 0.93, radiusMeters: 1700 },
      { lat: 9.865, lon: 75.850, probability: 0.78, radiusMeters: 2500 },
    ],
    suspects: [
      {
        id: 'vessel-kochi-1', mmsi: '538006240', name: 'MT Ocean Voyager',
        type: 'Crude Oil Tanker', flag: 'Marshall Islands (MH)',
        lengthMeters: 250, grossTonnage: 58000, lastCargo: 'Basrah Heavy Crude',
        isDarkVessel: false, attributionScore: 87, evidenceGrade: 'STRONG',
        driftAgreement: 91, timeOverlap: 89, spatialProximity: 85,
        vesselCharacteristics: 93, behavioralAnomaly: 77,
        distanceToOriginKm: 1.2, timeDiffMinutes: 18,
        keyEvidence: [
          'Transited within 1.2 km of hindcast centroid along international tanker fairway',
          'De-ballasting signature confirmed by satellite infrared differential',
          'Discharge velocity matches hydrodynamic trajectory displacement',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 9.800, lon: 75.900, timestamp: '2025-05-26T04:30:00Z', sogKnots: 13.4, cogDegrees: 325 },
          { lat: 9.858, lon: 75.858, timestamp: '2025-05-26T06:15:00Z', sogKnots: 10.8, cogDegrees: 322 },
          { lat: 9.925, lon: 75.815, timestamp: '2025-05-26T08:30:00Z', sogKnots: 13.6, cogDegrees: 320 },
          { lat: 9.995, lon: 75.765, timestamp: '2025-05-26T11:00:00Z', sogKnots: 13.8, cogDegrees: 320 },
        ],
      },
    ],
    summaryNotes: 'High-traffic international corridor attribution with verified tanker origin.',
    severity: 'HIGH',
  },
  {
    id: 'vizag-2019',
    title: 'Visakhapatnam SPM Crude Discharge',
    regionName: 'Vizag Outer Roadstead · Bay of Bengal (15km Offshore)',
    incidentDate: '2019-08-11',
    detectionTimestamp: '2019-08-11T07:45:00Z',
    estimatedReleaseWindow: {
      start: '2019-08-11T02:30:00Z', end: '2019-08-11T04:15:00Z',
      hoursBeforeDetection: 4.5,
    },
    centerLat: 17.640, centerLon: 83.460, zoomLevel: 11,
    slickPolygon: [
      [17.670, 83.440], [17.655, 83.485], [17.620, 83.490],
      [17.610, 83.450], [17.635, 83.430],
    ],
    slickAreaKm2: 18.2, slickPerimeterKm: 17.5,
    estimatedVolumeBarrels: 480, estimatedAgeHours: 4.6,
    fpFilterConfidence: 0.954, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Coastal Wave Shadow Filter',
    windU10: -3.8, windV10: -2.4, windSpeedKnots: 9.8, windDirectionDeg: 55,
    oceanCurrentSpeedKnots: 0.9, oceanCurrentDirDeg: 210,
    seaSurfaceTempC: 28.8, waveHeightM: 1.1,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 17.640, lon: 83.460, timestamp: '2019-08-11T07:45:00Z', uncertaintyRadiusKm: 0.6 },
      { hoursFromDetection: -2.0, lat: 17.660, lon: 83.450, timestamp: '2019-08-11T05:45:00Z', uncertaintyRadiusKm: 1.4 },
      { hoursFromDetection: -4.5, lat: 17.685, lon: 83.438, timestamp: '2019-08-11T03:15:00Z', uncertaintyRadiusKm: 2.6 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 17.640, lon: 83.460, timestamp: '2019-08-11T07:45:00Z', uncertaintyRadiusKm: 0.6 },
      { hoursFromDetection: 6.0, lat: 17.605, lon: 83.475, timestamp: '2019-08-11T13:45:00Z', uncertaintyRadiusKm: 2.4 },
      { hoursFromDetection: 12.0, lat: 17.565, lon: 83.490, timestamp: '2019-08-11T19:45:00Z', uncertaintyRadiusKm: 4.6 },
      { hoursFromDetection: 24.0, lat: 17.480, lon: 83.520, timestamp: '2019-08-12T07:45:00Z', uncertaintyRadiusKm: 8.2 },
    ],
    originHeatmap: [
      { lat: 17.685, lon: 83.438, probability: 0.95, radiusMeters: 1400 },
      { lat: 17.675, lon: 83.445, probability: 0.81, radiusMeters: 2200 },
    ],
    suspects: [
      {
        id: 'vessel-vizag-1', mmsi: '419082000', name: 'MT Ratna Puja',
        type: 'Crude Oil Tanker', flag: 'India (IN)',
        lengthMeters: 220, grossTonnage: 44000, lastCargo: 'Domestic Offshore Crude',
        isDarkVessel: false, attributionScore: 89, evidenceGrade: 'STRONG',
        driftAgreement: 93, timeOverlap: 91, spatialProximity: 88,
        vesselCharacteristics: 90, behavioralAnomaly: 82,
        distanceToOriginKm: 0.9, timeDiffMinutes: 14,
        keyEvidence: [
          'SPM crude transfer line disconnection observed at 03:20 UTC',
          'Vessel draft shift of 0.4m consistent with pipeline backflow',
          'Centroid coordinates align 93% with backward Eulerian drift model',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 17.580, lon: 83.495, timestamp: '2019-08-11T01:30:00Z', sogKnots: 10.4, cogDegrees: 330 },
          { lat: 17.688, lon: 83.436, timestamp: '2019-08-11T03:20:00Z', sogKnots: 0.5, cogDegrees: 180 },
          { lat: 17.675, lon: 83.442, timestamp: '2019-08-11T05:30:00Z', sogKnots: 1.1, cogDegrees: 160 },
          { lat: 17.635, lon: 83.465, timestamp: '2019-08-11T07:45:00Z', sogKnots: 8.2, cogDegrees: 145 },
        ],
      },
    ],
    summaryNotes: 'SPM crude discharge incident confirmed with high-confidence AIS and drift correlation.',
    severity: 'MEDIUM',
  },
  {
    id: 'paradip-2026',
    title: 'Paradip Port Offshore Pipeline Leak',
    regionName: 'Paradip Offshore Deepwater Basin · Bay of Bengal',
    incidentDate: '2026-05-22',
    detectionTimestamp: '2026-05-22T06:30:00Z',
    estimatedReleaseWindow: {
      start: '2026-05-22T01:00:00Z', end: '2026-05-22T03:00:00Z',
      hoursBeforeDetection: 4.5,
    },
    centerLat: 20.220, centerLon: 86.890, zoomLevel: 11,
    slickPolygon: [
      [20.250, 86.870], [20.235, 86.915], [20.200, 86.920],
      [20.190, 86.880], [20.215, 86.860],
    ],
    slickAreaKm2: 22.8, slickPerimeterKm: 21.0,
    estimatedVolumeBarrels: 710, estimatedAgeHours: 4.8,
    fpFilterConfidence: 0.948, isVerifiedOil: true,
    lookalikeCategoryChecked: 'Estuarine Organic Film Rejection',
    windU10: -4.5, windV10: -1.8, windSpeedKnots: 10.4, windDirectionDeg: 68,
    oceanCurrentSpeedKnots: 1.0, oceanCurrentDirDeg: 215,
    seaSurfaceTempC: 29.0, waveHeightM: 1.2,
    backwardDriftPath: [
      { hoursFromDetection: 0, lat: 20.220, lon: 86.890, timestamp: '2026-05-22T06:30:00Z', uncertaintyRadiusKm: 0.7 },
      { hoursFromDetection: -2.0, lat: 20.245, lon: 86.878, timestamp: '2026-05-22T04:30:00Z', uncertaintyRadiusKm: 1.5 },
      { hoursFromDetection: -4.5, lat: 20.275, lon: 86.862, timestamp: '2026-05-22T02:00:00Z', uncertaintyRadiusKm: 2.8 },
    ],
    forwardDriftForecast: [
      { hoursFromDetection: 0, lat: 20.220, lon: 86.890, timestamp: '2026-05-22T06:30:00Z', uncertaintyRadiusKm: 0.7 },
      { hoursFromDetection: 6.0, lat: 20.180, lon: 86.910, timestamp: '2026-05-22T12:30:00Z', uncertaintyRadiusKm: 2.6 },
      { hoursFromDetection: 12.0, lat: 20.135, lon: 86.930, timestamp: '2026-05-22T18:30:00Z', uncertaintyRadiusKm: 4.9 },
      { hoursFromDetection: 24.0, lat: 20.040, lon: 86.970, timestamp: '2026-05-23T06:30:00Z', uncertaintyRadiusKm: 8.8 },
    ],
    originHeatmap: [
      { lat: 20.275, lon: 86.862, probability: 0.96, radiusMeters: 1600 },
      { lat: 20.265, lon: 86.872, probability: 0.79, radiusMeters: 2400 },
    ],
    suspects: [
      {
        id: 'vessel-paradip-1', mmsi: '419075000', name: 'MT Jag Aparna',
        type: 'Crude Oil Tanker', flag: 'India (IN)',
        lengthMeters: 232, grossTonnage: 47500, lastCargo: 'Import Crude',
        isDarkVessel: false, attributionScore: 88, evidenceGrade: 'STRONG',
        driftAgreement: 92, timeOverlap: 90, spatialProximity: 86,
        vesselCharacteristics: 91, behavioralAnomaly: 80,
        distanceToOriginKm: 1.1, timeDiffMinutes: 16,
        keyEvidence: [
          'Offshore pipeline manifold transit during pressure loss spike',
          'Vessel course alteration of 35° coincident with release window',
          'Hindcast drift trajectory intersects historical track within 1.1 km',
        ],
        disqualificationReasons: [],
        track: [
          { lat: 20.140, lon: 86.950, timestamp: '2026-05-22T00:30:00Z', sogKnots: 12.8, cogDegrees: 325 },
          { lat: 20.278, lon: 86.860, timestamp: '2026-05-22T02:00:00Z', sogKnots: 2.4, cogDegrees: 290 },
          { lat: 20.260, lon: 86.872, timestamp: '2026-05-22T04:00:00Z', sogKnots: 1.2, cogDegrees: 170 },
          { lat: 20.215, lon: 86.892, timestamp: '2026-05-22T06:30:00Z', sogKnots: 9.6, cogDegrees: 155 },
        ],
      },
    ],
    summaryNotes: 'Deepwater crude discharge attribution with verifiable satellite radar telemetry.',
    severity: 'HIGH',
  },
];

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function createVesselIcon(vessel: SuspectVessel, isSelected: boolean) {
  const isDemoTanker = vessel.id === 'demo-vessel-primary';
  const isTop = vessel.attributionScore >= 80;
  const isDark = vessel.isDarkVessel;

  if (isDemoTanker) {
    return L.divIcon({
      className: 'custom-vessel-marker',
      html: `
        <div class="relative flex items-center justify-center cursor-pointer select-none">
          <div class="absolute w-20 h-20 rounded-full bg-rose-600/20 border border-rose-500/50 animate-ping"></div>
          <div class="absolute w-14 h-14 rounded-full bg-rose-500/25 border-2 border-rose-500 animate-pulse"></div>
          <div class="relative w-12 h-12 rounded-2xl bg-gradient-to-br from-rose-600 via-rose-700 to-amber-700 border-2 border-rose-300 shadow-[0_0_35px_rgba(244,63,94,0.95)] flex items-center justify-center text-white">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 drop-shadow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1 .6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>
              <path d="M19.38 20A11.6 11.6 0 0 0 21 14l-9-4-9 4c0 2.9.94 5.34 2.81 7.76"/>
              <path d="M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6"/>
              <path d="M12 10v4"/>
              <path d="M12 2v3"/>
            </svg>
            <span class="absolute -top-1 -right-1 flex h-4 w-4">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-80"></span>
              <span class="relative inline-flex rounded-full h-4 w-4 bg-rose-500 border-2 border-white"></span>
            </span>
          </div>
          <div class="absolute top-14 left-1/2 -translate-x-1/2 whitespace-nowrap px-3 py-1 rounded-lg bg-slate-950/95 border-2 border-rose-500 shadow-2xl flex items-center space-x-1.5 pointer-events-none">
            <span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
            <span class="text-xs font-mono font-black text-rose-200 tracking-wider">MV SARASWATI STAR [LEAKING]</span>
          </div>
        </div>
      `,
      iconSize: [48, 48],
      iconAnchor: [24, 24],
      popupAnchor: [0, -28],
    });
  }

  let bgClass = 'bg-blue-600';
  let borderClass = 'border-blue-400';
  let pulseHtml = '';
  if (isDark) {
    bgClass = 'bg-amber-600'; borderClass = 'border-amber-400';
    pulseHtml = '<span class="absolute -top-1 -right-1 flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span></span>';
  } else if (isTop) {
    bgClass = 'bg-rose-600'; borderClass = 'border-rose-400';
    pulseHtml = '<span class="absolute -top-1 -right-1 flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span></span>';
  }
  const ring = isSelected ? 'ring-4 ring-cyan-400 ring-offset-2 ring-offset-slate-950 scale-125' : '';
  return L.divIcon({
    className: 'custom-vessel-marker',
    html: `<div class="relative flex items-center justify-center cursor-pointer transition-transform duration-200 ${ring}"><div class="w-8 h-8 rounded-full ${bgClass} border-2 ${borderClass} shadow-lg shadow-black/60 flex items-center justify-center text-white"><svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1 .6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.38 20A11.6 11.6 0 0 0 21 14l-9-4-9 4c0 2.9.94 5.34 2.81 7.76"/><path d="M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6"/><path d="M12 10v4"/><path d="M12 2v3"/></svg></div>${pulseHtml}</div>`,
    iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -20],
  });
}

function getInterpolatedPosition(track: TrackPoint[], timeOffsetRatio: number): [number, number] {
  if (!track || track.length === 0) return [0, 0];
  if (track.length === 1) return [track[0].lat, track[0].lon];
  const iFloat = timeOffsetRatio * (track.length - 1);
  const li = Math.floor(iFloat);
  const ui = Math.min(li + 1, track.length - 1);
  const f = iFloat - li;
  return [
    track[li].lat + f * (track[ui].lat - track[li].lat),
    track[li].lon + f * (track[ui].lon - track[li].lon),
  ];
}

const MapViewUpdater: React.FC<{ center: [number, number]; zoom: number }> = ({ center, zoom }) => {
  const map = useMap();
  useEffect(() => { map.flyTo(center, zoom, { duration: 1.2 }); }, [center, zoom, map]);
  return null;
};

const severityColor = (sev: string) => {
  switch (sev) {
    case 'CRITICAL': return 'text-rose-400 bg-rose-950/60 border-rose-700/60';
    case 'HIGH': return 'text-amber-400 bg-amber-950/60 border-amber-700/60';
    case 'MEDIUM': return 'text-yellow-400 bg-yellow-950/60 border-yellow-700/60';
    default: return 'text-emerald-400 bg-emerald-950/60 border-emerald-700/60';
  }
};

function generateOffshoreSlick(lat: number, lon: number, dLon: number): LatLng[] {
  const oLon = lon + dLon;
  return [
    [lat + 0.015, oLon - 0.01],
    [lat + 0.020, oLon + 0.015],
    [lat + 0.008, oLon + 0.030],
    [lat - 0.010, oLon + 0.035],
    [lat - 0.020, oLon + 0.020],
    [lat - 0.018, oLon - 0.005],
    [lat - 0.005, oLon - 0.015],
    [lat + 0.008, oLon - 0.012],
  ];
}

function generateOffshoreOrigin(lat: number, lon: number, dLon: number): OriginHeatmapPoint[] {
  const oLon = lon + dLon * 1.3;
  return [
    { lat, lon: oLon, probability: 0.95, radiusMeters: 1500 },
    { lat: lat + 0.015, lon: oLon + 0.015, probability: 0.75, radiusMeters: 2400 },
    { lat: lat - 0.012, lon: oLon - 0.010, probability: 0.55, radiusMeters: 3200 },
  ];
}

const UTCClock: React.FC = () => {
  const [utc, setUtc] = useState('');
  useEffect(() => {
    const tick = () => {
      const n = new Date();
      setUtc(`${String(n.getUTCHours()).padStart(2, '0')}:${String(n.getUTCMinutes()).padStart(2, '0')}:${String(n.getUTCSeconds()).padStart(2, '0')}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="flex items-center space-x-2 px-2.5 py-1.5 rounded-lg bg-slate-800/90 border border-cyan-700/60 text-cyan-300 font-mono text-[11px] font-bold">
      <Clock className="w-3 h-3 text-cyan-400" />
      <span>UTC {utc}</span>
    </div>
  );
};

const LiveEventTicker: React.FC<{ incident: IncidentCase }> = ({ incident }) => {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [paused, setPaused] = useState(false);

  const generateEvent = (): LogEvent => {
    const now = new Date();
    const time = `${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}:${String(now.getUTCSeconds()).padStart(2, '0')}`;
    const types: Omit<LogEvent, 'time'>[] = [
      { level: 'info', message: `AIS TARGET ${incident.suspects[Math.floor(Math.random() * incident.suspects.length)]?.mmsi} ping received` },
      { level: 'success', message: `SAR PASS S1-${Math.floor(Math.random() * 900 + 100)} processed — ${Math.floor(Math.random() * 30 + 10)} vessels detected` },
      { level: 'warn', message: `AIS GAP detected — ${Math.floor(Math.random() * 15 + 3)} min since last ping` },
      { level: 'info', message: `Drift simulation #${Math.floor(Math.random() * 9999)} complete — ${Math.floor(Math.random() * 400 + 100)} vectors` },
      { level: 'success', message: `Phase ${Math.floor(Math.random() * 6 + 1)} pipeline OK — ${(Math.random() * 3 + 0.5).toFixed(2)}s` },
      { level: 'warn', message: `Wind shift detected at ${(13 + Math.random()).toFixed(2)}°N, ${(80 + Math.random()).toFixed(2)}°E` },
      { level: 'info', message: `Slick extent updated: ${(incident.slickAreaKm2 + Math.random() * 2).toFixed(1)} km²` },
    ];
    return { time, ...types[Math.floor(Math.random() * types.length)] };
  };

  useEffect(() => {
    setEvents(Array.from({ length: 8 }, generateEvent));
    if (paused) return;
    const id = setInterval(() => {
      setEvents(prev => [generateEvent(), ...prev].slice(0, 30));
    }, 2500);
    return () => clearInterval(id);
  }, [paused, incident.id]);

  const levelColor = (lvl: string) => {
    switch (lvl) {
      case 'error': return 'text-rose-400';
      case 'warn': return 'text-amber-400';
      case 'success': return 'text-emerald-400';
      default: return 'text-cyan-400';
    }
  };

  return (
    <div className="h-9 bg-slate-950 border-t border-cyan-800/40 flex items-center overflow-hidden flex-shrink-0">
      <div className="flex items-center px-3 h-full border-r border-cyan-800/40 bg-cyan-950/30 flex-shrink-0">
        <Terminal className="w-3.5 h-3.5 text-cyan-400 mr-2" />
        <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">LIVE FEED</span>
      </div>
      <button onClick={() => setPaused(!paused)}
        className="px-2 h-full border-r border-cyan-800/40 hover:bg-slate-900 transition-colors"
        title={paused ? 'Resume feed' : 'Pause feed'}>
        {paused ? <Play className="w-3 h-3 text-amber-400" /> : <Pause className="w-3 h-3 text-cyan-400" />}
      </button>
      <div className="flex-1 overflow-hidden relative">
        <div className="absolute inset-0 flex items-center">
          <div className={`flex items-center space-x-6 whitespace-nowrap px-4 ${paused ? '' : 'animate-[tickerScroll_60s_linear_infinite]'}`}>
            {[...events, ...events].map((ev, i) => (
              <span key={i} className="flex items-center space-x-2 text-[11px] font-mono flex-shrink-0">
                <span className="text-slate-500">{ev.time}</span>
                <span className={levelColor(ev.level)}>●</span>
                <span className="text-slate-300">{ev.message}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
      <style>{`@keyframes tickerScroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }`}</style>
    </div>
  );
};

interface IncidentSidebarProps {
  incidents: IncidentCase[];
  selectedIncident: IncidentCase;
  onSelectIncident: (i: IncidentCase) => void;
  collapsed: boolean;
  onToggle: () => void;
}

const IncidentSidebar: React.FC<IncidentSidebarProps> = ({
  incidents, selectedIncident, onSelectIncident, collapsed, onToggle,
}) => {
  const [search, setSearch] = useState('');
  const filtered = incidents.filter(i =>
    i.title.toLowerCase().includes(search.toLowerCase()) ||
    i.regionName.toLowerCase().includes(search.toLowerCase())
  );

  if (collapsed) {
    return (
      <button onClick={onToggle}
        className="absolute top-4 left-4 z-[1001] glass-panel rounded-xl p-2.5 hover:border-cyan-500 transition-all">
        <ChevronRight className="w-5 h-5 text-cyan-400" />
      </button>
    );
  }

  return (
    <div className="absolute top-4 left-4 z-[1001] w-72 max-h-[calc(100%-8rem)] glass-panel rounded-2xl overflow-hidden flex flex-col">
      <div className="p-3 border-b border-slate-700/60 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-cyan-950 border border-cyan-700/60 flex items-center justify-center">
            <Satellite className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">Active Incidents</span>
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-700/60">
            {filtered.length}
          </span>
        </div>
        <button onClick={onToggle} className="p-1 rounded hover:bg-slate-800 text-slate-400">
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      <div className="p-2 border-b border-slate-700/60">
        <div className="flex items-center bg-slate-900/80 border border-slate-700/60 rounded-lg px-2">
          <Search className="w-3.5 h-3.5 text-slate-500" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search incidents..."
            className="flex-1 bg-transparent text-[11px] text-slate-100 px-2 py-1.5 focus:outline-none placeholder:text-slate-500" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {filtered.map(inc => {
          const isActive = inc.id === selectedIncident.id;
          const topSuspect = inc.suspects[0];
          return (
            <button key={inc.id} onClick={() => onSelectIncident(inc)}
              className={`w-full text-left p-2.5 rounded-xl transition-all border ${
                isActive
                  ? 'bg-cyan-950/40 border-cyan-600/60 shadow-lg shadow-cyan-900/30'
                  : 'bg-slate-900/60 border-slate-700/40 hover:border-slate-600 hover:bg-slate-900/90'
              }`}>
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${severityColor(inc.severity)}`}>
                  {inc.severity}
                </span>
                {isActive && (
                  <span className="flex items-center space-x-1 text-[9px] text-cyan-400 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                    ACTIVE
                  </span>
                )}
              </div>
              <div className="text-[11px] font-bold text-slate-100 leading-tight mb-1">{inc.title}</div>
              <div className="text-[10px] text-slate-400 mb-1.5 truncate">{inc.regionName}</div>
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="text-rose-400">{inc.slickAreaKm2.toFixed(1)} km²</span>
                <span className="text-slate-500">{inc.suspects.length} vessels</span>
              </div>
              {topSuspect && (
                <div className="mt-1.5 pt-1.5 border-t border-slate-700/40 flex items-center justify-between text-[10px]">
                  <span className="text-slate-300 truncate">{topSuspect.name}</span>
                  <span className="text-rose-400 font-bold">{topSuspect.attributionScore}</span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

interface AttributionFloatingProps {
  incident: IncidentCase;
  selectedVessel: SuspectVessel | null;
  onSelectVessel: (v: SuspectVessel) => void;
  collapsed: boolean;
  onToggle: () => void;
}

const AttributionFloatingPanel: React.FC<AttributionFloatingProps> = ({
  incident, selectedVessel, onSelectVessel, collapsed, onToggle,
}) => {
  const topVessel = incident.suspects[0];

  if (collapsed) {
    return (
      <button onClick={onToggle}
        className="absolute top-4 right-4 z-[1001] glass-panel rounded-xl p-2.5 hover:border-cyan-500 transition-all">
        <ChevronLeft className="w-5 h-5 text-cyan-400" />
      </button>
    );
  }

  return (
    <div className="absolute top-4 right-4 z-[1001] w-[420px] max-h-[calc(100%-8rem)] glass-panel rounded-2xl overflow-hidden flex flex-col">
      <div className="p-3 border-b border-slate-700/60 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-rose-950 border border-rose-700/60 flex items-center justify-center">
            <Award className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">Attribution Hub</span>
        </div>
        <button onClick={onToggle} className="p-1 rounded hover:bg-slate-800 text-slate-400">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {topVessel && (
          <div className="p-3 rounded-xl bg-gradient-to-br from-rose-950/40 via-slate-900 to-slate-900 border border-rose-600/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[9px] font-bold text-rose-400 uppercase tracking-wider px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-700/60">
                PRIMARY SUSPECT
              </span>
              <span className="text-[9px] font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-600/60 px-1.5 py-0.5 rounded">
                {topVessel.evidenceGrade}
              </span>
            </div>
            <div className="flex items-start space-x-2.5 mb-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-rose-600 to-amber-600 flex items-center justify-center flex-shrink-0">
                <Ship className="w-5 h-5 text-white" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-white truncate">{topVessel.name}</div>
                <div className="text-[10px] text-slate-400 font-mono">MMSI {topVessel.mmsi}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-2">
              <div className="bg-slate-900/70 rounded-lg p-2 text-center">
                <div className="text-[9px] text-slate-400 uppercase">Score</div>
                <div className="text-2xl font-extrabold text-rose-400 leading-none">{topVessel.attributionScore}</div>
              </div>
              <div className="bg-slate-900/70 rounded-lg p-2 text-center">
                <div className="text-[9px] text-slate-400 uppercase">Distance</div>
                <div className="text-sm font-bold text-white mt-0.5">{topVessel.distanceToOriginKm} km</div>
              </div>
            </div>

            <div className="h-32 -mx-2">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={[
                  { factor: 'Drift', value: topVessel.driftAgreement },
                  { factor: 'Time', value: topVessel.timeOverlap },
                  { factor: 'Space', value: topVessel.spatialProximity },
                  { factor: 'Type', value: topVessel.vesselCharacteristics },
                  { factor: 'Behav', value: topVessel.behavioralAnomaly },
                ]}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis dataKey="factor" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                  <RechartRadar dataKey="value" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.4} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        <div>
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 px-1">
            Other Candidates ({incident.suspects.length - 1})
          </div>
          <div className="space-y-1.5">
            {incident.suspects.slice(1).map((v, i) => (
              <button key={v.id} onClick={() => onSelectVessel(v)}
                className={`w-full text-left p-2 rounded-lg border transition-all ${
                  selectedVessel?.id === v.id
                    ? 'bg-cyan-950/40 border-cyan-600/50'
                    : 'bg-slate-900/60 border-slate-700/40 hover:border-slate-600'
                }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[9px] font-bold text-white px-1.5 py-0.5 rounded ${v.isDarkVessel ? 'bg-amber-600' : 'bg-slate-700'}`}>
                    #{i + 2}
                  </span>
                  <span className="text-[10px] font-bold text-slate-300">{v.attributionScore}/100</span>
                </div>
                <div className="text-[11px] font-semibold text-slate-200 truncate">{v.name}</div>
                <div className="text-[9px] text-slate-500 truncate">{v.type}</div>
                {v.disqualificationReasons.length > 0 && (
                  <div className="text-[9px] text-rose-400 mt-1 truncate">⚠ {v.disqualificationReasons[0]}</div>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-2 border-t border-slate-700/60 bg-slate-900/60">
        <div className="flex items-center justify-between text-[10px] font-mono">
          <span className="text-slate-400">Model v2.4.1</span>
          <span className="text-emerald-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>P1-P6 ONLINE</span>
          </span>
        </div>
      </div>
    </div>
  );
};

interface LayerControlsProps {
  activeLayers: any;
  toggleLayer: (k: string) => void;
  showPipelines: boolean;
  setShowPipelines: (v: boolean) => void;
}

const LayerControls: React.FC<LayerControlsProps> = ({ activeLayers, toggleLayer, showPipelines, setShowPipelines }) => {
  const [open, setOpen] = useState(true);

  const layers = [
    { key: 'spillPolygon', label: 'SAR Slick', color: 'bg-rose-500', active: activeLayers.spillPolygon },
    { key: 'originHeatmap', label: 'Origin Zone', color: 'bg-purple-500', active: activeLayers.originHeatmap },
    { key: 'backwardDrift', label: 'Hindcast', color: 'bg-indigo-500', active: activeLayers.backwardDrift },
    { key: 'forwardForecast', label: 'Forecast 24h', color: 'bg-cyan-400', active: activeLayers.forwardForecast },
    { key: 'aisTracks', label: 'AIS Tracks', color: 'bg-blue-500', active: activeLayers.aisTracks },
    { key: 'darkVessels', label: 'Dark Vessels', color: 'bg-amber-500', active: activeLayers.darkVessels },
    { key: 'windVectors', label: 'Wind Streamlines', color: 'bg-teal-400', active: activeLayers.windVectors !== false },
    { key: 'pipelines', label: 'Pipelines', color: 'bg-yellow-400', active: showPipelines },
  ];

  return (
    <div className="absolute bottom-24 left-4 z-[1001] w-56">
      <button onClick={() => setOpen(!open)}
        className="w-full glass-panel rounded-xl px-3 py-2 flex items-center justify-between hover:border-cyan-500 transition-all mb-1">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="text-[11px] font-bold text-slate-100 uppercase tracking-wider">Layers</span>
        </div>
        {open ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronUp className="w-3.5 h-3.5 text-slate-400" />}
      </button>

      {open && (
        <div className="glass-panel rounded-xl p-2 space-y-1">
          {layers.map(l => (
            <button key={l.key}
              onClick={() => l.key === 'pipelines' ? setShowPipelines(!showPipelines) : toggleLayer(l.key)}
              className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-slate-800/60 transition-colors">
              <div className="flex items-center space-x-2">
                <span className={`w-2.5 h-2.5 rounded-full ${l.color} ${l.active ? 'shadow-[0_0_8px_currentColor]' : 'opacity-30'}`}></span>
                <span className={`text-[10px] font-semibold ${l.active ? 'text-slate-100' : 'text-slate-500'}`}>{l.label}</span>
              </div>
              {l.active ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5 text-slate-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const StatusBar: React.FC<{ incident: IncidentCase }> = ({ incident }) => (
  <div className="absolute bottom-24 right-4 z-[1001] glass-panel rounded-xl px-3 py-2">
    <div className="flex items-center space-x-3 text-[10px] font-mono">
      <div className="flex items-center space-x-1">
        <MapPin className="w-3 h-3 text-cyan-400" />
        <span className="text-slate-400">LAT</span>
        <span className="text-slate-100 font-bold">{incident.centerLat.toFixed(4)}°N</span>
      </div>
      <div className="flex items-center space-x-1">
        <span className="text-slate-400">LON</span>
        <span className="text-slate-100 font-bold">{incident.centerLon.toFixed(4)}°E</span>
      </div>
      <div className="flex items-center space-x-1">
        <span className="text-slate-400">Z</span>
        <span className="text-cyan-300 font-bold">{incident.zoomLevel}</span>
      </div>
    </div>
  </div>
);

interface TimeMachineProps {
  incident: IncidentCase;
  timeOffsetRatio: number;
  onChangeRatio: React.Dispatch<React.SetStateAction<number>>;
}

const TimeMachineStrip: React.FC<TimeMachineProps> = ({ incident, timeOffsetRatio, onChangeRatio }) => {
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    let id: any = null;
    if (playing) {
      id = setInterval(() => {
        onChangeRatio((p) => {
          if (p >= 1.0) { setPlaying(false); return 1.0; }
          return Math.min(1.0, p + 0.015);
        });
      }, 100);
    }
    return () => { if (id) clearInterval(id); };
  }, [playing, onChangeRatio]);

  const totalHours = incident.estimatedReleaseWindow.hoursBeforeDetection;
  const currentOffset = -(totalHours * (1.0 - timeOffsetRatio));
  const detectionDate = new Date(incident.detectionTimestamp);
  const scrubbed = new Date(detectionDate.getTime() + currentOffset * 3600 * 1000);

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-4xl z-[1001]">
      <div className="glass-panel rounded-2xl p-3">
        <div className="flex items-center space-x-3">
          <button onClick={() => { if (timeOffsetRatio >= 1.0) onChangeRatio(0); setPlaying(!playing); }}
            className="w-10 h-10 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center shadow-lg flex-shrink-0 transition-all active:scale-95">
            {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current" />}
          </button>
          <button onClick={() => { setPlaying(false); onChangeRatio(0); }}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center justify-center flex-shrink-0">
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1 text-[10px]">
              <span className="text-purple-300 font-bold flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                <span>Origin (T-{totalHours}h)</span>
              </span>
              <span className="text-slate-100 font-mono font-bold">
                {currentOffset === 0 ? <span className="text-rose-400">T-0 DETECTION</span> : <span className="text-purple-300">T{currentOffset.toFixed(1)} hrs</span>}
              </span>
              <span className="text-rose-400 font-bold flex items-center space-x-1">
                <span>Detection (T-0)</span>
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
              </span>
            </div>
            <input type="range" min="0" max="1" step="0.005" value={timeOffsetRatio}
              onChange={(e) => { setPlaying(false); onChangeRatio(parseFloat(e.target.value)); }}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400" />
            <div className="flex items-center justify-between mt-1 text-[9px] text-slate-500 font-mono">
              <span>{new Date(incident.estimatedReleaseWindow.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} UTC</span>
              <span className="text-cyan-400">{scrubbed.toUTCString().slice(5, 22)}</span>
              <span>{new Date(incident.detectionTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} UTC</span>
            </div>
          </div>
          <button onClick={() => { setPlaying(false); onChangeRatio(1.0); }}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center justify-center flex-shrink-0">
            <FastForward className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

interface HeroMapProps {
  incident: IncidentCase;
  selectedVessel: SuspectVessel | null;
  onSelectVessel: (v: SuspectVessel) => void;
  timeOffsetRatio: number;
  activeLayers: any;
  showPipelines: boolean;
  demoSlickOpacity?: number;
  demoCameraTarget?: [number, number] | null;
  // Per-phase layer reveal: bits 0-5 map to phases 1-6
  // 0=hide all demo layers, 1=slick, 2=FP ring, 4=drift, 8=AIS tracks, 16=heatmap
  demoRevealedLayers?: number;
  // Multi-layer high-fidelity oil plume (sheen, core, spine, and expanding blooms)
  demoOilTrail?: DemoOilTrailData | null;
}

export interface DemoOilTrailData {
  sheen: [number, number][];
  core: [number, number][];
  spine: [number, number][];
  blooms: { center: [number, number]; radius: number; opacity: number }[];
}

// Fly-to helper used by demo mode to animate camera without re-mounting MapContainer
const MapFlyToTarget: React.FC<{ target: [number, number]; zoom?: number }> = ({ target, zoom = 12 }) => {
  const map = useMap();
  useEffect(() => {
    map.flyTo(target, zoom, { duration: 2.0 });
  }, [target, zoom, map]);
  return null;
};

const HeroMap: React.FC<HeroMapProps> = ({
  incident, selectedVessel, onSelectVessel, timeOffsetRatio,
  activeLayers, showPipelines, demoSlickOpacity, demoCameraTarget,
  demoRevealedLayers, demoOilTrail,
}) => {
  const center: [number, number] = [incident.centerLat, incident.centerLon];
  const backwardCoords = useMemo(() => incident.backwardDriftPath.map((p): [number, number] => [p.lat, p.lon]), [incident]);
  const forwardCoords = useMemo(() => incident.forwardDriftForecast.map((p): [number, number] => [p.lat, p.lon]), [incident]);
  const [basemap, setBasemap] = useState<'dark' | 'satellite' | 'osm'>('satellite');

  // Demo mode: use demoRevealedLayers bitmask to gate rendering
  // When undefined (non-demo), fall back to normal activeLayers logic
  const isDemo = demoRevealedLayers !== undefined;
  const showSlick       = isDemo ? !!(demoRevealedLayers & 1)  : (activeLayers.spillPolygon && incident.isVerifiedOil);
  const showDrift       = isDemo ? !!(demoRevealedLayers & 4)  : (activeLayers.backwardDrift && incident.isVerifiedOil);
  const showForecast    = isDemo ? false                        : (activeLayers.forwardForecast && incident.isVerifiedOil);
  const showHeatmap     = isDemo ? !!(demoRevealedLayers & 16) : activeLayers.originHeatmap;
  const showAisTracks   = isDemo ? !!(demoRevealedLayers & 8)  : activeLayers.aisTracks;
  const showVesselMarks = isDemo ? !!(demoRevealedLayers & 8)  : true;

  return (
    <MapContainer center={center} zoom={incident.zoomLevel} scrollWheelZoom className="w-full h-full">
      <MapViewUpdater center={center} zoom={incident.zoomLevel} />

      {/* ── TACTICAL WIND & OCEAN CURRENT VECTOR STREAMLINES ── */}
      <TacticalWindOverlay incident={incident} visible={activeLayers.windVectors !== false} />

      {basemap === 'dark' && (
        <>
          <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}" maxZoom={16} />
          <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}" maxZoom={16} />
        </>
      )}
      {basemap === 'satellite' && (
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxZoom={18} />
      )}
      {basemap === 'osm' && (
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} />
      )}

      {demoCameraTarget && <MapFlyToTarget target={demoCameraTarget} zoom={12} />}

      {/* ── HIGH-FIDELITY OIL SLICK PLUME (multi-layer organic diffusion) ── */}
      {isDemo && demoOilTrail && demoOilTrail.sheen.length >= 3 && (
        <Polygon
          positions={demoOilTrail.sheen}
          pathOptions={{
            color: '#0284c7',
            weight: 1.5,
            opacity: 0.55,
            fillColor: '#0a2136',
            fillOpacity: 0.45,
          }}
        />
      )}
      {isDemo && demoOilTrail && demoOilTrail.core.length >= 3 && (
        <Polygon
          positions={demoOilTrail.core}
          pathOptions={{
            color: '#0f172a',
            weight: 2,
            opacity: 0.9,
            fillColor: '#020617',
            fillOpacity: 0.92,
          }}
        />
      )}
      {isDemo && demoOilTrail && demoOilTrail.spine.length >= 2 && (
        <Polyline
          positions={demoOilTrail.spine}
          pathOptions={{
            color: '#000000',
            weight: 6.5,
            opacity: 0.98,
            lineCap: 'round',
          }}
        />
      )}
      {isDemo && demoOilTrail && demoOilTrail.blooms?.map((bloom, bIdx) => (
        <Circle
          key={`bloom-${bIdx}`}
          center={bloom.center}
          radius={bloom.radius}
          pathOptions={{
            color: '#38bdf8',
            weight: 1.5,
            opacity: 0.45,
            fillColor: '#030712',
            fillOpacity: bloom.opacity,
          }}
        />
      ))}

      {/* ── SLICK POLYGON ── */}
      {showSlick && incident.slickPolygon.length >= 3 && (
        <Polygon
          positions={incident.slickPolygon}
          pathOptions={{
            color: '#f43f5e', weight: 2, fillColor: '#f43f5e',
            fillOpacity: demoSlickOpacity !== undefined ? demoSlickOpacity * 0.45 : 0.45,
            opacity: demoSlickOpacity !== undefined ? demoSlickOpacity : 1,
            dashArray: '4, 4',
          }}
        >
          <Tooltip permanent direction="center" className="bg-transparent border-0 shadow-none font-mono text-xs text-rose-300 font-bold">
            Slick ({incident.slickAreaKm2.toFixed(1)} km²)
          </Tooltip>
        </Polygon>
      )}

      {/* ── PHASE 2: FP CONFIDENCE RING ── */}
      {isDemo && !!(demoRevealedLayers & 2) && (
        <Circle
          center={[incident.centerLat, incident.centerLon]}
          radius={3200}
          pathOptions={{ color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.07, weight: 1.5, dashArray: '4,4' }}
        >
          <Tooltip permanent direction="top" className="font-mono text-xs text-cyan-300 font-bold bg-slate-900/80 px-2 py-1 rounded border border-cyan-700/60">
            FP Filter: 94.3% confidence — Verified Oil
          </Tooltip>
        </Circle>
      )}

      {/* ── BACKWARD DRIFT ── */}
      {showDrift && backwardCoords.length >= 2 && (
        <Polyline positions={backwardCoords} pathOptions={{ color: '#a855f7', weight: 3, dashArray: '6, 6', opacity: 0.85 }} />
      )}

      {/* ── FORWARD FORECAST (non-demo only) ── */}
      {showForecast && forwardCoords.length >= 2 && (
        <>
          <Polyline positions={forwardCoords} pathOptions={{ color: '#06b6d4', weight: 2.5, dashArray: '4, 6', opacity: 0.85 }} />
          {incident.forwardDriftForecast.map((step, i) => {
            if (step.hoursFromDetection === 0) return null;
            return (
              <Circle key={i} center={[step.lat, step.lon]} radius={step.uncertaintyRadiusKm * 1000}
                pathOptions={{ color: '#06b6d4', fillColor: '#22d3ee', fillOpacity: 0.15, weight: 1.5, dashArray: '3, 4' }}>
                <Tooltip permanent direction="top" className="font-mono text-[10px] text-cyan-300 font-bold bg-slate-900/80 px-1 py-0.5 rounded border border-cyan-700/60">
                  T+{step.hoursFromDetection}h
                </Tooltip>
              </Circle>
            );
          })}
        </>
      )}

      {/* ── ORIGIN HEATMAP ── */}
      {showHeatmap && incident.originHeatmap.map((heat, i) => (
        <Circle key={i} center={[heat.lat, heat.lon]} radius={heat.radiusMeters}
          pathOptions={{ color: i === 0 ? '#9333ea' : '#7e22ce', fillColor: i === 0 ? '#a855f7' : '#c084fc', fillOpacity: i === 0 ? 0.4 : 0.18, weight: 1 }}>
          {i === 0 && (
            <Tooltip permanent direction="top" className="font-mono text-xs text-purple-200 font-bold">
              Origin ({(heat.probability * 100).toFixed(0)}%)
            </Tooltip>
          )}
        </Circle>
      ))}

      {/* ── AIS TRACKS ── */}
      {showAisTracks && incident.suspects.map((v) => {
        const coords = v.track.map((t): [number, number] => [t.lat, t.lon]);
        let color = '#3b82f6';
        if (v.isDarkVessel) color = '#f59e0b';
        else if (v.attributionScore >= 80) color = '#f43f5e';
        return (
          <Polyline key={v.id} positions={coords}
            pathOptions={{ color, weight: v.attributionScore >= 80 ? 3 : 2, dashArray: v.isDarkVessel ? '2, 4' : undefined, opacity: selectedVessel?.id === v.id ? 1 : 0.6 }} />
        );
      })}

      {/* ── VESSEL MARKERS ── */}
      {showVesselMarks && incident.suspects.map((v) => {
        if (v.isDarkVessel && !activeLayers.darkVessels) return null;
        const pos = getInterpolatedPosition(v.track, timeOffsetRatio);
        return (
          <Marker key={v.id} position={pos} icon={createVesselIcon(v, selectedVessel?.id === v.id)} eventHandlers={{ click: () => onSelectVessel(v) }}>
            <Popup>
              <div className="text-xs space-y-1 min-w-[180px]">
                <div className="font-bold text-slate-100">{v.name}</div>
                <div className="text-slate-300 font-mono text-[11px]">MMSI: {v.mmsi}</div>
                <div className="text-rose-400 font-bold">Score: {v.attributionScore}/100</div>
              </div>
            </Popup>
          </Marker>
        );
      })}

      {/* ── SUBSEA PIPELINES (strictly offshore) ── */}
      {showPipelines && (
        <>
          <Polyline
            positions={
              incident.centerLon < 75
                ? [
                    [19.20, 71.35],
                    [19.35, 71.45],
                    [19.50, 71.55],
                  ]
                : [
                    [incident.centerLat - 0.15, incident.centerLon + 0.05],
                    [incident.centerLat, incident.centerLon + 0.08],
                    [incident.centerLat + 0.18, incident.centerLon + 0.12],
                  ]
            }
            pathOptions={{ color: '#facc15', weight: 2.2, dashArray: '8, 6', opacity: 0.65 }}
          />
        </>
      )}

      {/* Basemap selector */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] glass-panel rounded-xl p-1 flex items-center space-x-1">
        {(['dark', 'satellite', 'osm'] as const).map((m) => (
          <button key={m} onClick={() => setBasemap(m)}
            className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
              basemap === m ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}>
            {m === 'osm' ? 'OSM' : m}
          </button>
        ))}
      </div>
    </MapContainer>
  );
};

const ModalRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/40">
    <span className="text-slate-400">{label}</span>
    <span className="text-slate-100 font-semibold font-mono">{value}</span>
  </div>
);

const AttributionFullPage: React.FC<{
  incident: IncidentCase;
  selectedVessel: SuspectVessel | null;
  onSelectVessel: (v: SuspectVessel) => void;
}> = ({ incident, selectedVessel, onSelectVessel }) => {
  const topVessel = incident.suspects[0];
  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-700/60 flex items-center justify-center text-cyan-400">
          <Award className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">Vessel Attribution</h2>
          <p className="text-xs text-slate-400">Multi-factor drift & AIS correlation</p>
        </div>
      </div>

      {topVessel && (
        <div className="p-6 rounded-2xl border-2 bg-gradient-to-br from-rose-950/30 via-slate-900 to-slate-900 border-rose-500/70">
          <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
            <span className="px-3 py-1 bg-gradient-to-r from-rose-600 to-red-600 text-white text-xs font-bold rounded-lg flex items-center space-x-1.5">
              <Shield className="w-3.5 h-3.5" /><span>PRIMARY SUSPECT • RANK #1</span>
            </span>
            <span className="text-xs font-bold text-emerald-400 bg-emerald-950/90 border border-emerald-600/70 px-3 py-1 rounded-lg">
              GRADE: {topVessel.evidenceGrade}
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mt-5">
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-start space-x-4">
                <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-rose-600 to-amber-600 flex items-center justify-center">
                  <Ship className="w-8 h-8 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="text-xl font-bold text-white">{topVessel.name}</h3>
                  <div className="flex items-center space-x-2 text-xs text-slate-300 mt-2 flex-wrap gap-y-1">
                    <span className="bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-cyan-300 font-semibold">MMSI: {topVessel.mmsi}</span>
                    <span className="bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-slate-300 font-semibold">{topVessel.flag}</span>
                    <span className="bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-slate-300 font-semibold">{topVessel.type}</span>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { l: 'Distance', v: `${topVessel.distanceToOriginKm} km` },
                  { l: 'Time Delta', v: `${topVessel.timeDiffMinutes} min` },
                  { l: 'Length', v: `${topVessel.lengthMeters} m` },
                  { l: 'Tonnage', v: `${topVessel.grossTonnage.toLocaleString()} GT` },
                ].map(x => (
                  <div key={x.l} className="bg-slate-900/80 p-3 rounded-lg border border-slate-700/60">
                    <div className="text-[10px] text-slate-400 uppercase font-bold">{x.l}</div>
                    <div className="text-base font-bold text-white mt-0.5">{x.v}</div>
                  </div>
                ))}
              </div>
              <div className="pt-3 border-t border-slate-700/80">
                <span className="text-xs text-slate-300 uppercase font-bold flex items-center mb-2">
                  <FileCheck className="w-4 h-4 mr-1.5 text-emerald-400" />Forensic Evidence
                </span>
                <ul className="space-y-1.5 text-xs text-slate-200">
                  {topVessel.keyEvidence.map((ev, i) => (
                    <li key={i} className="flex items-start space-x-2 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                      <span className="leading-snug">{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="space-y-3">
              <div className="p-4 bg-slate-900/80 rounded-xl border border-rose-700/40 text-center">
                <div className="text-[10px] text-slate-400 uppercase font-bold">Attribution Score</div>
                <div className="text-5xl font-extrabold text-rose-400 leading-none mt-1">{topVessel.attributionScore}</div>
                <div className="text-xs text-slate-500 mt-1">out of 100</div>
              </div>
              <div className="space-y-2">
                {[
                  { l: 'Drift', v: topVessel.driftAgreement, c: 'bg-cyan-400' },
                  { l: 'Temporal', v: topVessel.timeOverlap, c: 'bg-purple-400' },
                  { l: 'Spatial', v: topVessel.spatialProximity, c: 'bg-rose-400' },
                  { l: 'Type', v: topVessel.vesselCharacteristics, c: 'bg-amber-400' },
                  { l: 'Behavioral', v: topVessel.behavioralAnomaly, c: 'bg-emerald-400' },
                ].map(f => (
                  <div key={f.l}>
                    <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                      <span>{f.l}</span><strong className="text-cyan-300">{f.v}%</strong>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div className={`${f.c} h-full rounded-full`} style={{ width: `${f.v}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {incident.suspects.slice(1).map((v, i) => (
        <div key={v.id} onClick={() => onSelectVessel(v)}
          className={`rounded-2xl border p-4 cursor-pointer transition-all ${
            selectedVessel?.id === v.id ? 'bg-slate-800 border-cyan-500' : 'bg-slate-900/60 border-slate-700/60 hover:bg-slate-900'
          }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white text-sm ${v.isDarkVessel ? 'bg-amber-600' : 'bg-slate-700'}`}>#{i + 2}</div>
              <div>
                <h4 className="text-sm font-bold text-white">{v.name}</h4>
                <p className="text-xs text-slate-400">{v.type} • MMSI: {v.mmsi}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-base font-bold text-slate-200">{v.attributionScore}/100</div>
              <div className={`text-xs font-semibold ${v.evidenceGrade === 'STRONG' ? 'text-emerald-400' : v.evidenceGrade === 'INCONCLUSIVE' ? 'text-amber-400' : 'text-slate-400'}`}>{v.evidenceGrade}</div>
            </div>
          </div>
          {v.disqualificationReasons.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-700/60 flex items-start space-x-2 text-xs text-rose-400">
              <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>{v.disqualificationReasons[0]}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

const AIConsoleInline: React.FC<{ incident: IncidentCase }> = ({ incident }) => {
  const [messages, setMessages] = useState<Array<{ role: 'bot' | 'user'; text: string }>>([
    { role: 'bot', text: `Spill detected at ${incident.regionName}. Confidence 92%. Ask me anything.` },
  ]);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const send = () => {
    const t = input.trim();
    if (!t) return;
    setInput('');
    setMessages((p) => [...p, { role: 'user', text: t }]);
    setTimeout(() => {
      const top = incident.suspects[0];
      const reply = top
        ? `Primary suspect: ${top.name} (MMSI ${top.mmsi}), score ${top.attributionScore}/100. Evidence: ${top.keyEvidence[0]}`
        : 'No verified oil spill in scene.';
      setMessages((p) => [...p, { role: 'bot', text: reply }]);
    }, 700);
  };

  return (
    <div className="h-full w-full p-6 bg-slate-950 overflow-hidden">
      <div className="max-w-6xl mx-auto h-full flex flex-col space-y-4">
        <div className="flex items-center space-x-3 flex-shrink-0">
          <div className="w-10 h-10 rounded-xl bg-purple-950 border border-purple-700/60 flex items-center justify-center text-purple-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">AI Investigation Console</h2>
            <p className="text-xs text-slate-400">Chat with the forensic pipeline</p>
          </div>
        </div>
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 overflow-hidden min-h-0">
          <div className="lg:col-span-2 flex flex-col bg-slate-900/60 border border-purple-800/50 rounded-2xl overflow-hidden">
            <div className="flex items-center space-x-2 px-4 py-2.5 border-b border-purple-800/50 bg-purple-950/40">
              <Bot className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-bold text-purple-300 uppercase tracking-wider">Chat</span>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((m, i) => (
                <div key={i} className={`flex items-start space-x-2 text-sm ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {m.role === 'bot' && (
                    <div className="w-7 h-7 rounded-full bg-purple-900 flex items-center justify-center flex-shrink-0">
                      <Bot className="w-4 h-4 text-purple-300" />
                    </div>
                  )}
                  <div className={`px-3 py-2 rounded-lg max-w-[80%] leading-snug ${m.role === 'user' ? 'bg-cyan-950 text-cyan-100 border border-cyan-700/60' : 'bg-slate-800 text-slate-200 border border-slate-700/60'}`}>
                    {m.text}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center border-t border-slate-800">
              <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
                placeholder="Ask about this incident..."
                className="flex-1 bg-transparent text-sm text-slate-100 px-4 py-3 focus:outline-none placeholder:text-slate-500" />
              <button onClick={send} className="p-3 text-cyan-400 hover:text-cyan-300">
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="space-y-4 overflow-y-auto">
            <div className="bg-slate-900/60 border border-emerald-800/50 rounded-xl p-4">
              <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                <Database className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold text-emerald-300 uppercase tracking-wider">Dataset</span>
              </div>
              <div className="space-y-2 text-[11px]">
                <ModalRow label="AIS Records" value="1,247,892" />
                <ModalRow label="SAR Passes" value="18" />
                <ModalRow label="Drift Vectors" value="342" />
              </div>
            </div>
            <div className="bg-slate-900/60 border border-cyan-800/50 rounded-xl p-4">
              <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider">System Health</span>
              </div>
              <div className="space-y-1.5 text-[11px]">
                {['SAR U-Net', 'FP Filter', 'Drift Hindcast', 'AIS Correlation', 'Attribution', 'Dossier'].map((p, i) => (
                  <div key={p} className="flex items-center justify-between py-1 border-b border-slate-800/40">
                    <span className="text-slate-300">P{i + 1} — {p}</span>
                    <span className="flex items-center space-x-1.5 text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span className="font-bold text-[10px]">ONLINE</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const AnalyticsInline: React.FC<{ incident: IncidentCase }> = ({ incident }) => {
  const spillGrowth = incident.forwardDriftForecast.map(s => ({
    hour: s.hoursFromDetection === 0 ? 'T-0' : `T+${s.hoursFromDetection}`,
    area: parseFloat((incident.slickAreaKm2 * (1 + s.hoursFromDetection * 0.02)).toFixed(1)),
  }));

  const windData = Array.from({ length: 12 }, (_, i) => ({
    hour: `${String(i * 2).padStart(2, '0')}:00`,
    speed: 8 + Math.sin(i / 3) * 3 + Math.random() * 2,
    current: 0.7 + Math.cos(i / 4) * 0.3 + Math.random() * 0.2,
  }));

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-700/60 flex items-center justify-center text-cyan-400">
          <BarChart3 className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">Analytics</h2>
          <p className="text-xs text-slate-400">Telemetry & drift visualization</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatBox label="Slick Extent" value={`${incident.slickAreaKm2} km²`} sub={`~${incident.estimatedVolumeBarrels} bbls`} color="text-rose-400" />
        <StatBox label="Age" value={`${incident.estimatedAgeHours} hrs`} sub={`Release ~${incident.estimatedReleaseWindow.hoursBeforeDetection}h prior`} color="text-amber-400" />
        <StatBox label="FP Confidence" value={`${(incident.fpFilterConfidence * 100).toFixed(1)}%`} sub="Verified oil" color="text-emerald-400" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ChartCard title="Spill Area Growth" subtitle="Predicted slick extent">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={spillGrowth}>
              <defs>
                <linearGradient id="spillGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.5} />
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} />
              <RechartTooltip contentStyle={{ background: '#0a0f1a', border: '1px solid #1e293b', fontSize: '11px' }} />
              <Area type="monotone" dataKey="area" stroke="#f43f5e" strokeWidth={2} fill="url(#spillGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Wind & Current" subtitle="Telemetry over time">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={windData}>
              <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} />
              <RechartTooltip contentStyle={{ background: '#0a0f1a', border: '1px solid #1e293b', fontSize: '11px' }} />
              <Line type="monotone" dataKey="speed" stroke="#06b6d4" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="current" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ChartCard title="Meteorological Telemetry" subtitle="ERA5 reanalysis">
          <div className="space-y-1.5 text-[11px]">
            <ModalRow label="Wind Speed" value={`${incident.windSpeedKnots} kn`} />
            <ModalRow label="Wind Direction" value={`${incident.windDirectionDeg}°`} />
            <ModalRow label="U10 Component" value={`${incident.windU10} m/s`} />
            <ModalRow label="V10 Component" value={`${incident.windV10} m/s`} />
            <ModalRow label="Sea Surface Temp" value={`${incident.seaSurfaceTempC}°C`} />
            <ModalRow label="Wave Height" value={`${incident.waveHeightM} m`} />
          </div>
        </ChartCard>
        <ChartCard title="Ocean Current Data" subtitle="HYCOM surface currents">
          <div className="space-y-1.5 text-[11px]">
            <ModalRow label="Current Speed" value={`${incident.oceanCurrentSpeedKnots} kn`} />
            <ModalRow label="Current Direction" value={`${incident.oceanCurrentDirDeg}°`} />
            <ModalRow label="Slick Perimeter" value={`${incident.slickPerimeterKm} km`} />
            <ModalRow label="Lookalike" value={incident.lookalikeCategoryChecked} />
            <ModalRow label="Region" value={incident.regionName} />
            <ModalRow label="Detection" value={new Date(incident.detectionTimestamp).toUTCString().slice(0, 22)} />
          </div>
        </ChartCard>
      </div>
    </div>
  );
};

const StatBox: React.FC<{ label: string; value: string; sub: string; color: string }> = ({ label, value, sub, color }) => (
  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
    <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">{label}</div>
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    <div className="text-[10px] text-slate-500 mt-1">{sub}</div>
  </div>
);

const ChartCard: React.FC<{ title: string; subtitle: string; children: React.ReactNode }> = ({ title, subtitle, children }) => (
  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
    <div className="mb-3">
      <div className="text-xs font-bold text-slate-100">{title}</div>
      <div className="text-[10px] text-slate-500">{subtitle}</div>
    </div>
    {children}
  </div>
);

// ============================================================
// REPORTS INLINE — LIGHT DOSSIER · NAVY BLUE ACCENTS
// ============================================================
const ReportsInline: React.FC<{ incident: IncidentCase }> = ({ incident }) => {
  const top = incident.suspects[0];
  const handlePrint = () => window.print();
  const now = new Date();
  const reportRef = `NTRO/ICG/SIH-26143/${incident.id.toUpperCase()}/${now.getFullYear()}`;

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between no-print">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950 border border-indigo-700/60 flex items-center justify-center text-indigo-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">Intelligence Dossier</h2>
            <p className="text-xs text-slate-400">Official maritime forensic report · 8 sections · print-ready</p>
          </div>
        </div>
        <button onClick={handlePrint}
          className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold shadow-lg">
          <Printer className="w-3.5 h-3.5" /><span>Print / Export</span>
        </button>
      </div>

      <div className="dossier-print-target">
        <div className="dossier-page rounded-xl overflow-hidden relative">
          {/* Classification top banner — NAVY BLUE */}
          <div className="flex items-center justify-between px-8 py-2" style={{ background: '#1e3a8a' }}>
            <span className="text-[9px] font-bold tracking-[0.3em] text-blue-100 font-mono">RESTRICTED // MARITIME INTELLIGENCE</span>
            <span className="text-[9px] font-bold tracking-[0.3em] text-blue-100 font-mono">HANDLE VIA NTRO CHANNELS ONLY</span>
          </div>

          <div className="dossier-watermark">CLASSIFIED</div>

          <div className="p-8 md:p-12 relative z-10">
            {/* LETTERHEAD */}
            <div className="dossier-letterhead flex items-start justify-between pb-6 mb-8">
              <div className="flex items-start space-x-4">
                <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #1e3a8a, #3b82f6)', boxShadow: '0 0 30px rgba(59,130,246,0.4)' }}>
                  <Shield className="w-9 h-9 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-black tracking-tight text-slate-900" style={{ fontFamily: 'Georgia, serif' }}>
                    INDIAN COAST GUARD
                  </h1>
                  <p className="text-xs tracking-widest uppercase mt-1 text-blue-800 font-mono">
                    Directorate of Maritime Intelligence
                  </p>
                  <p className="text-[10px] mt-1 text-slate-500 font-mono">
                    NTRO / SIH-26143 · Marine Surveillance Division
                  </p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[9px] font-bold tracking-[0.2em] text-blue-800 font-mono">
                  FORENSIC DOSSIER
                </div>
                <div className="text-[10px] mt-1 text-slate-600 font-mono">
                  REF: {reportRef}
                </div>
                <div className="text-[10px] mt-0.5 text-slate-500 font-mono">
                  {now.toUTCString().slice(5, 22)} UTC
                </div>
              </div>
            </div>

            {/* 1. EXECUTIVE SUMMARY */}
            <ReportSection number="01" title="Executive Summary">
              <div className="p-5 rounded-r" style={{ background: 'rgba(30,58,138,0.06)', borderLeft: '4px solid #1e3a8a' }}>
                <p className="text-sm leading-relaxed text-slate-700" style={{ fontFamily: 'Georgia, serif' }}>
                  On <strong className="text-slate-900">{new Date(incident.detectionTimestamp).toUTCString().slice(5, 22)}</strong>, satellite SAR reconnaissance identified a significant oil spill of <strong className="text-blue-800">{incident.slickAreaKm2} km²</strong> within <strong className="text-slate-900">{incident.regionName}</strong> at coordinates <strong className="text-cyan-800 font-mono">{incident.centerLat.toFixed(3)}°N, {incident.centerLon.toFixed(3)}°E</strong>. Following six-phase forensic attribution across SAR imagery, drift hindcasting, and AIS tracking, the primary source vessel is identified as <strong className="text-slate-900">{top?.name ?? 'unknown'}</strong> (MMSI <span className="font-mono">{top?.mmsi ?? 'N/A'}</span>) with <strong className="text-blue-800">{top?.attributionScore ?? 0}/100</strong> confidence and <strong className="text-emerald-700">{top?.evidenceGrade ?? 'N/A'}</strong> evidence grade. Estimated release volume: <strong className="text-blue-800">~{incident.estimatedVolumeBarrels.toLocaleString()} barrels</strong>.
                </p>
              </div>
            </ReportSection>

            {/* 2. INCIDENT PROFILE */}
            <ReportSection number="02" title="Incident Profile">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <InfoCell label="Case ID" value={`SIH-26143-${incident.id.toUpperCase()}`} />
                <InfoCell label="Severity" value={incident.severity} valueColor="text-blue-800" />
                <InfoCell label="Detection (UTC)" value={new Date(incident.detectionTimestamp).toUTCString().slice(5, 22)} />
                <InfoCell label="Age" value={`${incident.estimatedAgeHours} hours`} />
                <InfoCell label="Center" value={`${incident.centerLat.toFixed(3)}°N, ${incident.centerLon.toFixed(3)}°E`} span={2} />
                <InfoCell label="Release Window" value={`T-${incident.estimatedReleaseWindow.hoursBeforeDetection}h prior`} />
                <InfoCell label="FP Confidence" value={`${(incident.fpFilterConfidence * 100).toFixed(1)}%`} valueColor="text-emerald-700" />
                <InfoCell label="Slick Area" value={`${incident.slickAreaKm2} km²`} valueColor="text-blue-800" />
                <InfoCell label="Perimeter" value={`${incident.slickPerimeterKm} km`} />
                <InfoCell label="Volume Est." value={`${incident.estimatedVolumeBarrels.toLocaleString()} bbl`} />
                <InfoCell label="Lookalike" value={incident.lookalikeCategoryChecked} />
              </div>
            </ReportSection>

            {/* 3. ENVIRONMENTAL CONDITIONS */}
            <ReportSection number="03" title="Environmental Conditions (ERA5 + HYCOM Reanalysis)">
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                <MiniCell label="Wind" value={`${incident.windSpeedKnots} kn`} />
                <MiniCell label="Dir" value={`${incident.windDirectionDeg}°`} />
                <MiniCell label="U10" value={`${incident.windU10}`} />
                <MiniCell label="V10" value={`${incident.windV10}`} />
                <MiniCell label="Wave" value={`${incident.waveHeightM} m`} />
                <MiniCell label="SST" value={`${incident.seaSurfaceTempC}°C`} />
                <MiniCell label="Current" value={`${incident.oceanCurrentSpeedKnots} kn`} />
                <MiniCell label="Cur Dir" value={`${incident.oceanCurrentDirDeg}°`} />
                <MiniCell label="Slick Perim" value={`${incident.slickPerimeterKm} km`} />
                <MiniCell label="Verified" value={incident.isVerifiedOil ? 'YES' : 'NO'} />
                <MiniCell label="SAR Pass" value="S1-442" />
                <MiniCell label="Lookalike" value="Resolved" />
              </div>
            </ReportSection>

            {/* 4. FORENSIC PIPELINE */}
            <ReportSection number="04" title="Six-Phase Forensic Pipeline">
              <div className="space-y-1.5">
                {[
                  { n: '1', name: 'SAR Segmentation (U-Net)', result: `${incident.suspects.length + 21} vessels detected` },
                  { n: '2', name: 'False-Positive Filter (CNN)', result: `${(incident.fpFilterConfidence * 100).toFixed(1)}% confidence` },
                  { n: '3', name: 'Drift Hindcast (Backward)', result: `Origin recovered T-${incident.estimatedReleaseWindow.hoursBeforeDetection}h` },
                  { n: '4', name: 'AIS Correlation & Dark Vessel', result: `${incident.suspects.length} candidates flagged` },
                  { n: '5', name: 'Multi-Factor Attribution', result: `Rank #1: ${top?.name ?? 'N/A'}` },
                  { n: '6', name: 'Evidence Dossier Generation', result: `Ref ${reportRef}` },
                ].map(p => (
                  <div key={p.n} className="flex items-center space-x-3 px-3 py-2 rounded" style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                    <div className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold text-white" style={{ background: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                      {p.n}
                    </div>
                    <div className="flex-1 text-xs font-semibold text-slate-800">{p.name}</div>
                    <div className="text-[11px] text-emerald-800 font-mono">{p.result}</div>
                    <CheckCircle2 className="w-3.5 h-3.5" style={{ color: '#10b981' }} />
                  </div>
                ))}
              </div>
            </ReportSection>

            {/* 5. RANKED CANDIDATES */}
            <ReportSection number="05" title="Ranked Candidate Vessels">
              <div className="overflow-hidden rounded" style={{ border: '1px solid rgba(30, 58, 138, 0.3)' }}>
                <table className="w-full">
                  <thead>
                    <tr style={{ background: 'rgba(30, 58, 138, 0.12)' }}>
                      <th className="text-left px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">RANK</th>
                      <th className="text-left px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">VESSEL</th>
                      <th className="text-left px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">MMSI</th>
                      <th className="text-left px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">TYPE</th>
                      <th className="text-left px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">FLAG</th>
                      <th className="text-right px-3 py-2 text-[9px] font-bold tracking-wider text-blue-800 font-mono">SCORE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incident.suspects.map((v, i) => (
                      <tr key={v.id} style={{
                        background: i === 0 ? 'rgba(30, 58, 138, 0.06)' : i % 2 === 0 ? 'rgba(241, 245, 249, 0.5)' : 'transparent',
                        borderTop: '1px solid rgba(203, 213, 225, 0.6)'
                      }}>
                        <td className="px-3 py-2 text-xs font-bold font-mono" style={{ color: i === 0 ? '#1e40af' : '#64748b' }}>
                          #{i + 1}
                        </td>
                        <td className="px-3 py-2 text-xs font-bold text-slate-900">
                          {v.name}
                          {v.isDarkVessel && <span className="ml-2 text-[8px] px-1.5 py-0.5 rounded font-bold text-white" style={{ background: '#f59e0b' }}>DARK</span>}
                        </td>
                        <td className="px-3 py-2 text-[11px] text-cyan-800 font-mono">{v.mmsi}</td>
                        <td className="px-3 py-2 text-[10px] text-slate-600">{v.type}</td>
                        <td className="px-3 py-2 text-[10px] text-slate-600">{v.flag}</td>
                        <td className="px-3 py-2 text-right text-sm font-bold font-mono" style={{ color: i === 0 ? '#1e40af' : '#475569' }}>
                          {v.attributionScore}/100
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ReportSection>

            {/* 6. PRIMARY SUSPECT DETAIL */}
            {top && (
              <ReportSection number="06" title="Primary Suspect — Detailed Evidence">
                <div className="rounded p-5" style={{ background: 'rgba(30, 58, 138, 0.05)', border: '1px solid rgba(30, 58, 138, 0.35)' }}>
                  <div className="flex items-start justify-between mb-5">
                    <div className="flex items-center space-x-4">
                      <div className="w-14 h-14 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #1e3a8a, #3b82f6)', boxShadow: '0 0 20px rgba(59,130,246,0.3)' }}>
                        <Ship className="w-7 h-7 text-white" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-slate-900">{top.name}</h3>
                        <p className="text-[10px] mt-0.5 text-slate-600 font-mono">
                          MMSI: {top.mmsi} · FLAG: {top.flag}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-4xl font-black leading-none text-blue-800 font-mono">{top.attributionScore}</div>
                      <div className="text-[9px] mt-1 font-bold tracking-wider text-slate-500 font-mono">OUT OF 100</div>
                      <div className="text-[9px] mt-1 font-bold px-2 py-0.5 rounded text-white" style={{ background: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                        GRADE: {top.evidenceGrade}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                    <DetailBox label="Length" value={`${top.lengthMeters} m`} />
                    <DetailBox label="Tonnage" value={`${top.grossTonnage.toLocaleString()} GT`} />
                    <DetailBox label="Dist to Origin" value={`${top.distanceToOriginKm} km`} />
                    <DetailBox label="Time Δ" value={`${top.timeDiffMinutes} min`} />
                  </div>

                  <div className="mb-5">
                    <div className="text-[10px] font-bold tracking-wider mb-2 text-blue-800 font-mono">DECLARED CARGO</div>
                    <div className="px-3 py-2 rounded text-xs text-amber-800 font-mono" style={{ background: 'rgba(255, 251, 235, 0.8)', border: '1px solid rgba(30, 58, 138, 0.25)' }}>
                      {top.lastCargo}
                    </div>
                  </div>

                  <div className="mb-5">
                    <div className="text-[10px] font-bold tracking-wider mb-2 text-blue-800 font-mono">FORENSIC EVIDENCE CHAIN</div>
                    <ul className="space-y-1.5">
                      {top.keyEvidence.map((ev, i) => (
                        <li key={i} className="flex items-start space-x-2 px-3 py-2 rounded text-xs text-slate-800" style={{ background: 'rgba(240, 253, 244, 0.7)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#10b981' }} />
                          <span>{ev}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <div className="text-[10px] font-bold tracking-wider mb-2 text-blue-800 font-mono">5-FACTOR ATTRIBUTION BREAKDOWN</div>
                    <div className="grid grid-cols-5 gap-2">
                      {[
                        { l: 'Drift', v: top.driftAgreement, w: '35%' },
                        { l: 'Time', v: top.timeOverlap, w: '25%' },
                        { l: 'Space', v: top.spatialProximity, w: '20%' },
                        { l: 'Type', v: top.vesselCharacteristics, w: '10%' },
                        { l: 'Behav', v: top.behavioralAnomaly, w: '10%' },
                      ].map(f => (
                        <div key={f.l} className="text-center p-2 rounded" style={{ background: 'rgba(248, 250, 252, 0.8)', border: '1px solid rgba(30, 58, 138, 0.25)' }}>
                          <div className="text-xl font-black leading-none text-cyan-800 font-mono">{f.v}</div>
                          <div className="text-[8px] mt-1 text-slate-600 font-mono">{f.l}</div>
                          <div className="text-[8px] text-slate-500 font-mono">w={f.w}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </ReportSection>
            )}

            {/* 7. RECOMMENDATIONS */}
            <ReportSection number="07" title="Recommendations & Immediate Action">
              <div className="space-y-2">
                {[
                  { urgency: 'IMMEDIATE', color: '#1e3a8a', action: `Deploy interceptor vessel to origin centroid (${incident.originHeatmap[0]?.lat.toFixed(3)}°N, ${incident.originHeatmap[0]?.lon.toFixed(3)}°E) for verification and containment.` },
                  { urgency: 'IMMEDIATE', color: '#1e3a8a', action: `Issue halt directive to ${top?.name ?? 'identified vessel'} — cease all cargo operations and standby at designated anchorage.` },
                  { urgency: '24 HRS', color: '#f59e0b', action: `Serve notice of violation under Maritime Safety Act §356 and Marine Pollution Prevention Regulations.` },
                  { urgency: '48 HRS', color: '#f59e0b', action: `Deploy oil spill response booms at predicted coastal impact zone (T+24h forecast coordinates).` },
                  { urgency: '72 HRS', color: '#64748b', action: `Submit complete evidentiary package to NTRO/ICG legal directorate for prosecution.` },
                ].map((r, i) => (
                  <div key={i} className="flex items-start space-x-3 px-3 py-2.5 rounded" style={{ background: 'rgba(248, 250, 252, 0.7)', border: '1px solid rgba(203, 213, 225, 0.6)' }}>
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded flex-shrink-0 tracking-wider text-white font-mono" style={{ background: r.color }}>
                      {r.urgency}
                    </span>
                    <span className="text-xs leading-relaxed text-slate-800" style={{ fontFamily: 'Georgia, serif' }}>
                      {r.action}
                    </span>
                  </div>
                ))}
              </div>
            </ReportSection>

            {/* 8. CERTIFICATION */}
            <ReportSection number="08" title="Certification & Signatures">
              <p className="text-xs leading-relaxed mb-6 text-slate-600" style={{ fontFamily: 'Georgia, serif' }}>
                This dossier summarizes algorithmic correlation between Synthetic Aperture Radar (SAR) imagery, hydrodynamic drift hindcasting, and Automatic Identification System (AIS) trajectories. It is intended strictly as decision support for maritime enforcement authorities and does not constitute final legal determination.
              </p>
              <div className="grid grid-cols-2 gap-12 mt-8">
                <div>
                  <div className="h-12 mb-2" style={{ borderBottom: '1px solid #1e3a8a' }} />
                  <div className="text-[10px] font-bold tracking-wider text-slate-900 font-mono">INVESTIGATING OFFICER</div>
                  <div className="text-[9px] mt-0.5 text-slate-500 font-mono">NTRO Marine Desk · Verified</div>
                  <div className="text-[9px] text-slate-500 font-mono">{now.toUTCString().slice(5, 22)} UTC</div>
                </div>
                <div>
                  <div className="h-12 mb-2" style={{ borderBottom: '1px solid #1e3a8a' }} />
                  <div className="text-[10px] font-bold tracking-wider text-slate-900 font-mono">APPROVING AUTHORITY</div>
                  <div className="text-[9px] mt-0.5 text-slate-500 font-mono">Director, Maritime Surveillance</div>
                  <div className="text-[9px] text-slate-500 font-mono">Digital approval pending</div>
                </div>
              </div>
            </ReportSection>

            {/* FOOTER */}
            <div className="mt-12 pt-4 flex items-center justify-between text-[9px] tracking-wider text-slate-500 font-mono" style={{ borderTop: '1px solid rgba(30, 58, 138, 0.3)' }}>
              <span>PAGE 1 OF 1 · {reportRef}</span>
              <span>GENERATED {now.toUTCString().slice(5, 22)} UTC</span>
              <span className="text-blue-800">RESTRICTED // FOR OFFICIAL USE ONLY</span>
            </div>
          </div>

          {/* Classification bottom banner — NAVY BLUE */}
          <div className="flex items-center justify-between px-8 py-2" style={{ background: '#1e3a8a' }}>
            <span className="text-[9px] font-bold tracking-[0.3em] text-blue-100 font-mono">RESTRICTED</span>
            <span className="text-[9px] font-bold tracking-[0.3em] text-blue-100 font-mono">SIH-26143 · NTRO</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const ReportSection: React.FC<{ number: string; title: string; children: React.ReactNode }> = ({ number, title, children }) => (
  <section className="mb-8 avoid-break">
    <div className="flex items-center mb-3">
      <div className="w-8 h-8 rounded flex items-center justify-center text-[11px] font-black mr-3 text-white font-mono" style={{ background: '#1e40af' }}>
        {number}
      </div>
      <h2 className="text-sm font-bold tracking-wider uppercase text-slate-900">
        {title}
      </h2>
      <div className="flex-1 ml-4 h-[1px]" style={{ background: 'linear-gradient(to right, rgba(30, 58, 138, 0.5), transparent)' }} />
    </div>
    <div>{children}</div>
  </section>
);

const InfoCell: React.FC<{ label: string; value: string; valueColor?: string; span?: number }> = ({ label, value, valueColor = 'text-slate-900', span = 1 }) => (
  <div className="px-3 py-2 rounded" style={{ background: 'rgba(248, 250, 252, 0.8)', border: '1px solid rgba(203, 213, 225, 0.7)', gridColumn: `span ${span}` }}>
    <div className="text-[9px] uppercase font-bold tracking-wider text-slate-500 font-mono">{label}</div>
    <div className={`text-xs font-bold mt-0.5 font-mono ${valueColor}`}>{value}</div>
  </div>
);

const MiniCell: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="px-2 py-1.5 rounded text-center" style={{ background: 'rgba(248, 250, 252, 0.8)', border: '1px solid rgba(203, 213, 225, 0.7)' }}>
    <div className="text-[8px] uppercase font-bold tracking-wider text-slate-500 font-mono">{label}</div>
    <div className="text-[11px] font-bold mt-0.5 truncate text-cyan-800 font-mono">{value}</div>
  </div>
);

const DetailBox: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="px-3 py-2 rounded" style={{ background: 'rgba(239, 246, 255, 0.7)', border: '1px solid rgba(30, 58, 138, 0.3)' }}>
    <div className="text-[9px] uppercase font-bold tracking-wider text-blue-800 font-mono">{label}</div>
    <div className="text-xs font-bold mt-0.5 text-slate-900 font-mono">{value}</div>
  </div>
);

// ============================================================
// INGEST INLINE — WITH IMAGE UPLOAD
// ============================================================
const IngestInline: React.FC<{ onIngested: (i: IncidentCase) => void }> = ({ onIngested }) => {
  const [sectorIdx, setSectorIdx] = useState(0);
  const [windSpeed, setWindSpeed] = useState(8);
  const [windDir, setWindDir] = useState(225);
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState(-1);
  const [done, setDone] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const sector = PRESET_SECTORS[sectorIdx];
  const PHASES = ['SAR Segmentation', 'FP Filtering', 'Drift Hindcast', 'AIS Correlation', 'Attribution', 'Dossier'];

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const clearFile = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleRun = async () => {
    setRunning(true); setDone(false); setPhase(0);
    for (let i = 0; i < PHASES.length; i++) {
      setPhase(i);
      await new Promise(r => setTimeout(r, 500));
    }

    const slickPolygon = generateOffshoreSlick(sector.lat, sector.lon, sector.dLon);
    const originHeatmap = generateOffshoreOrigin(sector.lat, sector.lon, sector.dLon);

    const baseLon = sector.lon + sector.dLon;
    const syntheticTracks: TrackPoint[] = [
      { lat: sector.lat + 0.02,   lon: baseLon - sector.dLon * 0.5, timestamp: new Date(Date.now() - 6 * 3600 * 1000).toISOString(), sogKnots: 12, cogDegrees: 220 },
      { lat: sector.lat + 0.01,   lon: baseLon - sector.dLon * 0.2, timestamp: new Date(Date.now() - 4 * 3600 * 1000).toISOString(), sogKnots: 6,  cogDegrees: 200 },
      { lat: sector.lat,          lon: baseLon,                      timestamp: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), sogKnots: 1.5, cogDegrees: 180 },
      { lat: sector.lat - 0.005,  lon: baseLon + sector.dLon * 0.2, timestamp: new Date(Date.now() - 1 * 3600 * 1000).toISOString(), sogKnots: 0.5, cogDegrees: 180 },
      { lat: sector.lat - 0.01,   lon: baseLon + sector.dLon * 0.3, timestamp: new Date().toISOString(), sogKnots: 0.2, cogDegrees: 180 },
    ];

    const synthetic: IncidentCase = {
      ...INCIDENT_CASES[0],
      id: `ingested-${Date.now()}`,
      title: `Live Ingest — ${sector.label}`,
      regionName: sector.label,
      centerLat: sector.lat + sector.dLon * 0.5,
      centerLon: sector.lon + sector.dLon * 0.7,
      zoomLevel: sector.zoom,
      detectionTimestamp: new Date().toISOString(),
      estimatedReleaseWindow: {
        start: new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
        end: new Date(Date.now() - 4 * 3600 * 1000).toISOString(),
        hoursBeforeDetection: 5,
      },
      slickPolygon,
      slickAreaKm2: 15 + Math.random() * 25,
      windSpeedKnots: windSpeed,
      windDirectionDeg: windDir,
      windU10: -Math.sin((windDir * Math.PI) / 180) * windSpeed * 0.5,
      windV10: -Math.cos((windDir * Math.PI) / 180) * windSpeed * 0.5,
      originHeatmap,
      suspects: INCIDENT_CASES[0].suspects.map((s, idx) => ({
        ...s,
        id: `ingested-${Date.now()}-${idx}`,
        distanceToOriginKm: 0.2 + Math.random() * 3,
        track: syntheticTracks.map(t => ({
          ...t,
          lat: t.lat + (idx - 1) * 0.003,
          lon: t.lon + (idx - 1) * 0.003,
        })),
      })),
      severity: 'HIGH',
    };
    onIngested(synthetic);
    setPhase(PHASES.length);
    setDone(true);
    setRunning(false);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-700/60 flex items-center justify-center text-cyan-400">
          <Satellite className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">Ingest Satellite Scene</h2>
          <p className="text-xs text-slate-400">Upload a SAR image and run the 6-phase forensic pipeline</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase mb-2 block flex items-center">
              <Upload className="w-3.5 h-3.5 inline mr-1.5 text-cyan-400" />
              Satellite SAR Image
            </label>

            {imagePreview ? (
              <div className="relative rounded-xl overflow-hidden border-2 border-emerald-500/60 bg-slate-950">
                <img src={imagePreview} alt="SAR preview" className="w-full h-64 object-cover" />
                <div className="absolute top-3 left-3 bg-emerald-600 text-white text-[10px] font-bold px-2 py-1 rounded-md flex items-center space-x-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>READY FOR PIPELINE</span>
                </div>
                <button onClick={clearFile}
                  className="absolute top-3 right-3 bg-rose-600 hover:bg-rose-500 text-white p-1.5 rounded-md">
                  <X className="w-3.5 h-3.5" />
                </button>
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-slate-950 to-transparent p-3">
                  <div className="text-xs text-emerald-300 font-bold truncate">{imageFile?.name}</div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    {imageFile ? (imageFile.size / 1024).toFixed(1) + ' KB' : ''} · {imageFile?.type}
                  </div>
                </div>
              </div>
            ) : (
              <div
                onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onClick={() => fileRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all h-64 flex flex-col items-center justify-center ${
                  drag ? 'border-cyan-400 bg-cyan-950/40 scale-[1.02]' : 'border-slate-700 hover:border-cyan-600 hover:bg-slate-800/60'
                }`}>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/tiff,image/webp"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                />
                <div className="w-16 h-16 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
                  <Upload className={`w-7 h-7 ${drag ? 'text-cyan-400' : 'text-slate-500'}`} />
                </div>
                <div className="text-sm font-bold text-slate-200">
                  {drag ? 'Drop to upload' : 'Drop SAR image here'}
                </div>
                <div className="text-xs text-slate-500 mt-1.5">
                  or <span className="text-cyan-400 underline">click to browse</span>
                </div>
                <div className="text-[10px] text-slate-600 mt-3 font-mono">
                  .png · .jpg · .tif · .webp · Max 20MB
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800">
            <MetaBox label="Acquisition" value={new Date().toISOString().slice(0, 10)} />
            <MetaBox label="Source" value="Sentinel-1 SAR" />
            <MetaBox label="Resolution" value="10 m/px" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase mb-2 block flex items-center">
              <MapPin className="w-3.5 h-3.5 inline mr-1.5 text-cyan-400" />
              Target Sector
            </label>
            <select value={sectorIdx} onChange={(e) => setSectorIdx(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:border-cyan-500">
              {PRESET_SECTORS.map((s, i) => (
                <option key={i} value={i} className="bg-slate-900">{s.label}</option>
              ))}
            </select>
            <div className="mt-1.5 text-[10px] text-slate-500 font-mono">
              Offshore: <strong className={sector.dLon > 0 ? 'text-cyan-300' : 'text-purple-300'}>
                {sector.dLon > 0 ? 'EAST (Bay of Bengal)' : 'WEST (Arabian Sea)'}
              </strong>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-bold text-slate-300 uppercase mb-2 block">Wind (kn)</label>
              <div className="flex items-center space-x-3">
                <input type="range" min="2" max="25" step="0.5" value={windSpeed} onChange={(e) => setWindSpeed(Number(e.target.value))} className="flex-1 accent-cyan-400" />
                <span className="text-cyan-300 font-bold text-sm w-10 text-right">{windSpeed}</span>
              </div>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-300 uppercase mb-2 block">Dir (°)</label>
              <div className="flex items-center space-x-3">
                <input type="range" min="0" max="359" step="1" value={windDir} onChange={(e) => setWindDir(Number(e.target.value))} className="flex-1 accent-cyan-400" />
                <span className="text-cyan-300 font-bold text-sm w-10 text-right">{windDir}°</span>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800">
            <div className="text-xs font-bold text-slate-300 uppercase mb-3">Pipeline Phases</div>
            <div className="space-y-1.5">
              {PHASES.map((p, i) => {
                const isDone = i < phase || (done && i < PHASES.length);
                const isActive = i === phase && !done;
                return (
                  <div key={i} className={`flex items-center space-x-2.5 text-xs px-2.5 py-1.5 rounded-lg transition-all ${
                    isDone ? 'bg-emerald-950/40 border border-emerald-800/60' :
                    isActive ? 'bg-cyan-950/40 border border-cyan-700/60' :
                    'bg-slate-800/40 border border-slate-700/40 opacity-50'
                  }`}>
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isDone ? 'bg-emerald-500' : isActive ? 'bg-cyan-500 animate-pulse' : 'bg-slate-700'
                    }`}>
                      {isDone ? <CheckCircle2 className="w-3 h-3 text-white" /> : <span className="text-white text-[10px] font-bold">{i + 1}</span>}
                    </div>
                    <span className={`font-medium ${isDone ? 'text-emerald-300' : isActive ? 'text-white' : 'text-slate-500'}`}>{p}</span>
                    {isActive && <Loader2 className="w-3 h-3 text-cyan-400 animate-spin ml-auto" />}
                  </div>
                );
              })}
            </div>
          </div>

          <button onClick={handleRun} disabled={running || !imageFile}
            className={`w-full flex items-center justify-center space-x-2 px-6 py-3 font-bold text-sm rounded-xl transition-all ${
              running ? 'bg-cyan-900/60 text-cyan-400 cursor-wait border border-cyan-700' :
              done ? 'bg-emerald-600 text-white' :
              !imageFile ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700' :
              'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-lg active:scale-95'
            }`}>
            {running ? (
              <><Loader2 className="w-4 h-4 animate-spin" /><span>Running Pipeline...</span></>
            ) : done ? (
              <><CheckCircle2 className="w-4 h-4" /><span>Ingested Successfully</span></>
            ) : !imageFile ? (
              <><Upload className="w-4 h-4" /><span>Upload Image to Begin</span></>
            ) : (
              <><Zap className="w-4 h-4 text-yellow-300" /><span>Execute Pipeline</span></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

const MetaBox: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="text-center">
    <div className="text-[9px] text-slate-500 uppercase font-bold">{label}</div>
    <div className="text-[11px] text-slate-200 font-mono mt-0.5">{value}</div>
  </div>
);

interface NavbarProps {
  selectedIncident: IncidentCase;
  allIncidents: IncidentCase[];
  onSelectIncident: (inc: IncidentCase) => void;
  isLiveBackend: boolean;
  wsConnected?: boolean;
  backendReachable?: boolean;
  pendingAlertCount?: number;
  onOpenAI: () => void;
  onOpenAnalytics: () => void;
  onOpenReports: () => void;
  onOpenIngest: () => void;
  onOpenSimulationVideo: () => void;
  onOpenCoastGuard: () => void;
  isDemoActive: boolean;
  onStartDemo: () => void;
  onStopDemo: () => void;
}

const Navbar: React.FC<NavbarProps> = ({
  selectedIncident,
  allIncidents,
  onSelectIncident,
  isLiveBackend,
  wsConnected = false,
  backendReachable = false,
  pendingAlertCount = 0,
  onOpenAI,
  onOpenAnalytics,
  onOpenReports,
  onOpenIngest,
  onOpenSimulationVideo,
  onOpenCoastGuard,
  isDemoActive,
  onStartDemo,
  onStopDemo,
}) => (
  <header className="h-14 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 px-4 flex items-center justify-between z-40 select-none flex-shrink-0 no-print">
    <div className="flex items-center space-x-3">
      <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-cyan-500/20 border border-cyan-400/40">
        <Shield className="w-5 h-5 text-white" />
      </div>
      <div>
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-bold tracking-wider px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-700/60 uppercase">NTRO • SIH-26143</span>
          <span className="flex items-center text-[10px] text-emerald-400 font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block mr-1"></span>
            {wsConnected ? 'WS ACTIVE' : 'RADAR ACTIVE'}
          </span>
        </div>
        <div className="text-xs font-bold text-white tracking-tight leading-tight">
          PAYODHI — Oil Spill Attribution System
        </div>
      </div>
    </div>

    {/* ── ALL INCIDENT CASES SELECTOR (Prominent Dropdown) ── */}
    <div className="flex-1 max-w-xl mx-4 hidden sm:block">
      <div className="flex items-center bg-slate-800/80 border border-slate-700/80 hover:border-cyan-500/60 rounded-xl px-3 py-1.5 transition-all shadow-md">
        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mr-2 flex items-center gap-1.5 whitespace-nowrap">
          <MapPin className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span>CASE:</span>
        </span>
        <select
          value={selectedIncident.id}
          onChange={(e) => {
            const found = allIncidents.find((i) => i.id === e.target.value);
            if (found) onSelectIncident(found);
          }}
          className="bg-transparent text-cyan-300 font-bold text-xs focus:outline-none cursor-pointer flex-1 truncate font-mono"
        >
          {allIncidents.map((inc) => (
            <option
              key={inc.id}
              value={inc.id}
              className="bg-slate-900 text-slate-100 py-1"
            >
              {inc.title} — {inc.regionName.split('·')[0].trim()}
            </option>
          ))}
        </select>
      </div>
    </div>

    <div className="flex items-center space-x-2">
      <UTCClock />
      <div className={`hidden md:flex items-center px-2.5 py-1.5 rounded-lg text-[10px] font-bold border ${
        wsConnected
          ? 'bg-emerald-950/80 text-emerald-300 border-emerald-600/70'
          : backendReachable
          ? 'bg-cyan-950/80 text-cyan-300 border-cyan-600/70'
          : 'bg-amber-950/80 text-amber-300 border-amber-600/70'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
          wsConnected
            ? 'bg-emerald-400 animate-pulse'
            : backendReachable
            ? 'bg-cyan-400 animate-pulse'
            : 'bg-amber-400'
        }`}></span>
        {wsConnected ? 'LIVE WS' : backendReachable ? 'LIVE API' : 'HYBRID DEMO'}
      </div>
      <div className="h-6 w-px bg-slate-800 mx-1"></div>

      {/* Coast Guard Alerts Button with Badge */}
      <button
        onClick={onOpenCoastGuard}
        title="Coast Guard Operations Desk"
        className="relative p-2 rounded-lg bg-slate-800/70 hover:bg-amber-950/60 border border-slate-700/60 hover:border-amber-600/60 text-slate-300 hover:text-amber-300 transition-all cursor-pointer"
      >
        <Shield className="w-4 h-4 text-amber-400" />
        {pendingAlertCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-black flex items-center justify-center animate-pulse">
            {pendingAlertCount}
          </span>
        )}
      </button>

      {/* Simulation Studio Video Button */}
      <button
        onClick={onOpenSimulationVideo}
        title="Hydrodynamic Simulation Video Studio"
        className="p-2 rounded-lg bg-slate-800/70 hover:bg-cyan-950/60 border border-slate-700/60 hover:border-cyan-600/60 text-slate-300 hover:text-cyan-300 transition-all cursor-pointer"
      >
        <Video className="w-4 h-4 text-cyan-400" />
      </button>

      <button onClick={onOpenAI} title="AI Console" className="p-2 rounded-lg bg-slate-800/70 hover:bg-purple-950/60 border border-slate-700/60 hover:border-purple-600/60 text-slate-300 hover:text-purple-300 transition-all cursor-pointer">
        <Bot className="w-4 h-4" />
      </button>
      <button onClick={onOpenAnalytics} title="Analytics" className="p-2 rounded-lg bg-slate-800/70 hover:bg-cyan-950/60 border border-slate-700/60 hover:border-cyan-600/60 text-slate-300 hover:text-cyan-300 transition-all cursor-pointer">
        <BarChart3 className="w-4 h-4" />
      </button>
      <button onClick={onOpenReports} title="Reports" className="p-2 rounded-lg bg-slate-800/70 hover:bg-indigo-950/60 border border-slate-700/60 hover:border-indigo-600/60 text-slate-300 hover:text-indigo-300 transition-all cursor-pointer">
        <FileText className="w-4 h-4" />
      </button>
      <button onClick={onOpenIngest} title="Ingest Scene" className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-[11px] font-bold shadow-lg shadow-cyan-900/30 active:scale-95 transition-all cursor-pointer">
        <Satellite className="w-3.5 h-3.5" />
        <span className="hidden md:inline">Ingest</span>
      </button>

      {/* ── DEMO MODE BUTTON ── */}
      {isDemoActive ? (
        <button
          onClick={onStopDemo}
          title="Stop Demo Mode"
          className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-amber-950/80 border border-amber-500 text-amber-300 text-[11px] font-bold hover:bg-amber-900/80 transition-all cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
          <span className="hidden md:inline">STOP</span>
        </button>
      ) : (
        <button
          onClick={onStartDemo}
          title="Start Demo Mode (or press D)"
          className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-900 border border-amber-500/70 text-amber-300 text-[11px] font-bold hover:border-amber-400 hover:bg-amber-950/40 transition-all animate-[demoPulse_2s_ease-in-out_infinite] cursor-pointer"
        >
          <Play className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
          <span className="hidden md:inline tracking-wider">DEMO</span>
        </button>
      )}
    </div>
  </header>
);

// ── DEMO SAR PAUSE MODAL ──────────────────────────────────────
interface DemoSarModalProps {
  onProceed: () => void;
}
const DemoSarModal: React.FC<DemoSarModalProps> = ({ onProceed }) => {
  const [dragging, setDragging] = useState(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    // Any file dropped counts as providing the SAR image
    onProceed();
  };
  return (
    <div className="absolute inset-0 z-[1020] flex items-center justify-center bg-slate-950/90 backdrop-blur-sm">
      <div className="w-full max-w-xl mx-6">
        {/* Header */}
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-cyan-900/60 border border-cyan-600/60 flex items-center justify-center">
            <Satellite className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="text-base font-black text-white tracking-tight">SAR Scene Input Required</div>
            <div className="text-xs text-slate-400 font-mono">Sentinel-1A · IW Mode · 2024-03-15T06:42Z</div>
          </div>
        </div>

        {/* Dropzone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={onProceed}
          className={`relative rounded-2xl border-2 border-dashed cursor-pointer transition-all overflow-hidden ${
            dragging
              ? 'border-cyan-400 bg-cyan-950/50'
              : 'border-slate-600 hover:border-cyan-600/70 bg-slate-900/60 hover:bg-slate-800/60'
          }`}
          style={{ minHeight: 180 }}
        >
          {/* Fake SAR greyscale thumbnail */}
          <div className="absolute inset-0 opacity-20"
            style={{
              background: 'repeating-linear-gradient(0deg, #0f172a 0px, #1e293b 2px, #0f172a 4px)',
            }}
          />
          <div className="relative z-10 flex flex-col items-center justify-center h-full py-10 space-y-3">
            <div className="w-16 h-16 rounded-xl bg-slate-800/80 border border-slate-600 flex items-center justify-center">
              <Upload className="w-7 h-7 text-slate-400" />
            </div>
            <div className="text-sm font-bold text-slate-300">Drop SAR GeoTIFF / PNG here</div>
            <div className="text-xs text-slate-500 font-mono">or click to auto-simulate</div>
          </div>
        </div>

        {/* Auto-proceed */}
        <button
          onClick={onProceed}
          className="mt-4 w-full flex items-center justify-center space-x-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-sm shadow-xl shadow-cyan-900/40 active:scale-95 transition-all"
        >
          <Zap className="w-4 h-4 text-yellow-300" />
          <span>Auto-Simulate SAR → Proceed with Pipeline</span>
        </button>
        <p className="text-center text-xs text-slate-600 mt-2 font-mono">
          No real SAR image? Click above — the pipeline runs on the pre-loaded demo scene.
        </p>
      </div>
    </div>
  );
};

// ── DEMO PIPELINE FLOATING PANEL ──────────────────────────────
interface DemoPipelinePanelProps {
  phases: DemoPhaseStatus[];
  sarBanner: boolean;
  showOriginPulse: boolean;
}
const DemoPipelinePanel: React.FC<DemoPipelinePanelProps> = ({ phases, sarBanner, showOriginPulse }) => {
  const completedCount = phases.filter(p => p.done).length;
  const activeIdx = phases.findIndex(p => p.active);
  const percent = Math.round((completedCount / phases.length) * 100);

  return (
    <div
      className="absolute bottom-5 right-5 z-[1002] w-96 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl transition-all duration-300 no-print"
      style={{
        background: 'rgba(3, 7, 18, 0.96)',
        border: '1px solid rgba(245, 158, 11, 0.45)',
        boxShadow: '0 0 50px rgba(0,0,0,0.85), 0 0 20px rgba(245, 158, 11, 0.15)',
      }}
    >
      {/* Top Banner */}
      <div className="px-4 py-3 border-b border-amber-600/30 bg-gradient-to-r from-amber-950/50 via-slate-900/60 to-amber-950/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
              <Radar className="w-4 h-4 text-amber-400 animate-pulse" />
            </div>
            <div>
              <div className="text-xs font-black text-amber-300 uppercase tracking-widest font-mono">
                FORENSIC PIPELINE
              </div>
              <div className="text-[10px] text-amber-400/70 font-mono">
                {completedCount === phases.length ? 'ALL 6 PHASES VERIFIED' : activeIdx >= 0 ? `EXECUTING PHASE ${activeIdx + 1} OF 6` : 'INITIALIZING...'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono font-black text-amber-400 bg-amber-950/80 px-2.5 py-1 rounded-md border border-amber-600/40">
              {percent}%
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-2.5 h-1.5 w-full bg-slate-800/80 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
          <div
            className="h-full bg-gradient-to-r from-cyan-400 via-amber-400 to-emerald-400 rounded-full transition-all duration-500 ease-out shadow-sm"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {sarBanner && (
        <div className="px-4 py-2 bg-cyan-950/60 border-b border-cyan-700/50 flex items-center space-x-2">
          <Satellite className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="text-xs text-cyan-200 font-mono font-bold tracking-tight">SAR PASS — Sentinel-1A · C-Band · 10m Ground Res</span>
        </div>
      )}

      {showOriginPulse && (
        <div className="px-4 py-2 bg-purple-950/70 border-b border-purple-600/50 flex items-center space-x-2">
          <MapPin className="w-4 h-4 text-purple-400 animate-bounce" />
          <span className="text-xs text-purple-200 font-mono font-bold">DISCHARGE ORIGIN — 13.340°N, 80.450°E</span>
        </div>
      )}

      {/* Phase List with BIG SMOOTH Checks */}
      <div className="p-3 space-y-2">
        {phases.map((ph, idx) => (
          <div
            key={ph.name}
            className={`flex items-center space-x-3 px-3 py-2.5 rounded-xl transition-all duration-500 ${
              ph.done
                ? 'bg-emerald-950/40 border border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.12)]'
                : ph.active
                ? 'bg-cyan-950/60 border border-cyan-400 shadow-[0_0_20px_rgba(6,182,212,0.25)] ring-1 ring-cyan-400/40'
                : 'bg-slate-900/40 border border-slate-800/40 opacity-40'
            }`}
          >
            {/* BIG BADGE */}
            <div
              className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-500 ${
                ph.done
                  ? 'bg-gradient-to-br from-emerald-400 to-teal-600 shadow-[0_0_16px_rgba(16,185,129,0.6)] text-white scale-100'
                  : ph.active
                  ? 'bg-gradient-to-br from-cyan-400 to-blue-600 animate-pulse-glow text-white'
                  : 'bg-slate-800/90 border border-slate-700/60 text-slate-400 font-mono text-xs font-bold'
              }`}
            >
              {ph.done ? (
                <Check className="w-5 h-5 text-white stroke-[3] animate-check-pop" />
              ) : ph.active ? (
                <Loader2 className="w-5 h-5 text-white animate-spin stroke-[2.5]" />
              ) : (
                <span>0{idx + 1}</span>
              )}
            </div>

            {/* Title and details */}
            <div className="flex-1 min-w-0">
              <div
                className={`text-xs font-bold tracking-wide leading-tight transition-colors duration-300 ${
                  ph.done ? 'text-emerald-200' : ph.active ? 'text-white' : 'text-slate-400'
                }`}
              >
                {ph.name}
              </div>
              {ph.sub && (
                <div
                  className={`text-[10px] font-mono leading-tight mt-0.5 ${
                    ph.done ? 'text-emerald-400/70' : ph.active ? 'text-cyan-300/80' : 'text-slate-500'
                  }`}
                >
                  {ph.sub}
                </div>
              )}
            </div>

            {/* Status / Timing */}
            <div>
              {ph.done ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-mono text-[11px] font-bold shadow-sm">
                  {ph.timing}
                </span>
              ) : ph.active ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-lg bg-cyan-950/90 border border-cyan-400/50 text-cyan-300 font-mono text-[10px] font-bold animate-pulse">
                  RUNNING
                </span>
              ) : (
                <span className="text-slate-600 font-mono text-[10px]">QUEUED</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── TARGET ACQUIRED OVERLAY ──────────────────────────────────
interface DemoTargetAcquiredProps {
  vessel: SuspectVessel;
  evidenceLine: number;
}
const DemoTargetAcquired: React.FC<DemoTargetAcquiredProps> = ({ vessel, evidenceLine }) => (
  <div className="absolute inset-0 z-[1010] flex items-center justify-center pointer-events-none">
    <div
      className="w-full max-w-2xl mx-6 rounded-2xl border-2 border-rose-500 overflow-hidden"
      style={{ background: 'rgba(2,6,23,0.98)', boxShadow: '0 0 80px rgba(244,63,94,0.45), 0 0 160px rgba(244,63,94,0.18)' }}
    >
      {/* Top strip */}
      <div className="flex items-center justify-between px-6 py-3 bg-rose-950/60 border-b border-rose-700/60">
        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-400 animate-pulse"></span>
          <span className="text-sm font-black text-rose-200 uppercase tracking-[0.2em] font-mono">TARGET ACQUIRED</span>
        </div>
        <span className="text-xs text-rose-400 font-mono">PRIMARY SUSPECT IDENTIFIED · SIH-26143</span>
      </div>

      <div className="p-6">
        <div className="flex items-start space-x-4 mb-5">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-rose-700 to-amber-700 flex items-center justify-center flex-shrink-0 border border-rose-500/60">
            <Ship className="w-10 h-10 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-2xl font-black text-white tracking-tight">{vessel.name}</div>
            <div className="text-sm text-slate-300 font-mono mt-1">MMSI {vessel.mmsi} · {vessel.type}</div>
            <div className="text-sm text-amber-300 font-mono mt-0.5">{vessel.flag} · Last Cargo: {vessel.lastCargo}</div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-6xl font-black text-rose-400 font-mono leading-none">{vessel.attributionScore}</div>
            <div className="text-xs text-slate-500 font-mono mt-1">OUT OF 100</div>
            <div className="mt-2 px-3 py-1 rounded-lg bg-emerald-900/70 border border-emerald-600/60 text-xs font-bold text-emerald-300 font-mono tracking-wider">
              GRADE: {vessel.evidenceGrade}
            </div>
          </div>
        </div>

        {/* Evidence chain */}
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 font-mono">Forensic Evidence Chain</div>
          {vessel.keyEvidence.map((ev, i) => (
            <div
              key={i}
              className="flex items-start space-x-2.5 px-4 py-2.5 rounded-xl bg-slate-900/80 border border-slate-700/60"
              style={{
                opacity: i < evidenceLine ? 1 : 0,
                transform: i < evidenceLine ? 'translateY(0)' : 'translateY(8px)',
                transition: 'opacity 0.45s ease, transform 0.45s ease',
              }}
            >
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-slate-200 leading-snug">{ev}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
);

// ── DEMO WATERMARK ────────────────────────────────────────────
const DemoWatermark: React.FC = () => (
  <div className="absolute top-3 left-3 z-[1003] flex items-center space-x-2 pointer-events-none no-print">
    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
    <span className="text-xs font-bold text-amber-400/80 uppercase tracking-[0.25em] font-mono">
      DEMO RECORDING MODE
    </span>
  </div>
);

// SAR incoming banner (shown at top of map content area)
const SarBanner: React.FC = () => (
  <div className="absolute top-0 left-0 right-0 z-[1009] flex items-center justify-center py-2.5 bg-cyan-950/95 border-b border-cyan-600/70">
    <Satellite className="w-4 h-4 text-cyan-400 mr-2 animate-pulse" />
    <span className="text-xs font-bold text-cyan-200 uppercase tracking-widest font-mono">
      SAR PASS INCOMING — SENTINEL-1A · IW MODE · 10m RESOLUTION
    </span>
    <span className="ml-3 w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
  </div>
);

interface TabBarProps {
  active: TabKey;
  onChange: (k: TabKey) => void;
  pendingAlertCount?: number;
}

const TabBar: React.FC<TabBarProps> = ({ active, onChange, pendingAlertCount = 0 }) => {
  const tabs: { key: TabKey; label: string; icon: React.ReactNode; badge?: number }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: <Sparkles className="w-4 h-4" /> },
    { key: 'map', label: 'Map View', icon: <LayoutDashboard className="w-4 h-4" /> },
    { key: 'simulation-video', label: 'Simulation Video', icon: <Video className="w-4 h-4" /> },
    { key: 'attribution', label: 'Attribution', icon: <Award className="w-4 h-4" /> },
    { key: 'cg-alerts', label: 'Coast Guard Ops', icon: <Shield className="w-4 h-4" />, badge: pendingAlertCount },
    { key: 'ai', label: 'AI Console', icon: <Bot className="w-4 h-4" /> },
    { key: 'analytics', label: 'Analytics', icon: <BarChart3 className="w-4 h-4" /> },
    { key: 'reports', label: 'Reports', icon: <FileText className="w-4 h-4" /> },
    { key: 'ingest', label: 'Ingest Scene', icon: <Satellite className="w-4 h-4" /> },
  ];

  return (
    <div className="bg-slate-900 border-b border-slate-800 px-4 flex items-center space-x-1 flex-shrink-0 overflow-x-auto no-print">
      {tabs.map((tab) => (
        <button key={tab.key} onClick={() => onChange(tab.key)}
          className={`flex items-center space-x-2 px-3.5 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all whitespace-nowrap cursor-pointer ${
            active === tab.key
              ? 'text-cyan-300 border-cyan-500 bg-cyan-950/20'
              : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-800/40'
          }`}>
          {tab.icon}
          <span>{tab.label}</span>
          {Boolean(tab.badge && tab.badge > 0) && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] font-black bg-rose-500 text-white animate-pulse">
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
};

export const App: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentCase[]>(INCIDENT_CASES);
  const [selectedIncident, setSelectedIncident] = useState<IncidentCase>(INCIDENT_CASES[0]);
  const [selectedVessel, setSelectedVessel] = useState<SuspectVessel | null>(INCIDENT_CASES[0].suspects[0] || null);
  const [isLiveBackend, setIsLiveBackend] = useState(false);
  const [timeOffsetRatio, setTimeOffsetRatio] = useState(1.0);
  const [showPipelines, setShowPipelines] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  // ── COAST GUARD & BACKEND LIVE STREAM ─────────────────────────────────────────
  const {
    alerts: cgAlerts,
    connected: wsConnected,
    backendReachable,
    acknowledge: acknowledgeCgAlert,
    triggerTestAlert,
    stations: cgStations,
  } = useResponses();

  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const pendingAlertCount = useMemo(() => {
    return cgAlerts.filter((a) => !a.ackedBy).length;
  }, [cgAlerts]);

  const handleAckCgAlert = async (alertId: string, officerId: string) => {
    await acknowledgeCgAlert(alertId, officerId);
  };

  const handleTriggerTestAlert = async () => {
    const alert = await triggerTestAlert({
      incident_id: selectedIncident.id,
      lat: selectedIncident.centerLat,
      lon: selectedIncident.centerLon,
      confidence: selectedIncident.fpFilterConfidence,
      top_suspect_name: selectedIncident.suspects[0]?.name,
    });
    if (alert) {
      setSelectedAlertId(alert.id);
    }
  };

  const [activeLayers, setActiveLayers] = useState({
    spillPolygon: true, backwardDrift: true, forwardForecast: true,
    originHeatmap: true, aisTracks: true, darkVessels: true,
    windVectors: true,
  });

  // ── DEMO STATE ──────────────────────────────────────────────────────────────
  const [demoActive, setDemoActive] = useState(false);
  const [demoSarBanner, setDemoSarBanner] = useState(false);
  const [demoSlickOpacity, setDemoSlickOpacity] = useState(1); // used only after SAR
  const [demoPipelinePhases, setDemoPipelinePhases] = useState<DemoPhaseStatus[]>(
    DEMO_PIPELINE_PHASES.map(p => ({ ...p, done: false, active: false }))
  );
  const [demoShowOriginPulse, setDemoShowOriginPulse] = useState(false);
  const [demoCameraTarget, setDemoCameraTarget] = useState<[number, number] | null>(null);
  const [demoShowTargetAcquired, setDemoShowTargetAcquired] = useState(false);
  const [demoEvidenceLine, setDemoEvidenceLine] = useState(0);
  const [demoShowPipelinePanel, setDemoShowPipelinePanel] = useState(false);
  const [demoShowSarTopBanner, setDemoShowSarTopBanner] = useState(false);
  // Growing oil trail (multi-layer organic plume revealed per tick as ship moves)
  const [demoOilTrail, setDemoOilTrail] = useState<DemoOilTrailData | null>(null);
  // Bitmask controlling which map layers are visible per phase
  // 0=none, 1=slick, 2=FP ring, 4=drift, 8=AIS tracks+markers, 16=heatmap
  const [demoRevealedLayers, setDemoRevealedLayers] = useState<number | undefined>(undefined);
  // Whether demo is paused at the SAR input step
  const [demoSarPaused, setDemoSarPaused] = useState(false);

  // Snapshot pre-demo state for restore on Stop
  const preDemo = useRef<{
    incidents: IncidentCase[];
    selectedIncident: IncidentCase;
    selectedVessel: SuspectVessel | null;
    activeTab: TabKey;
    timeOffsetRatio: number;
  } | null>(null);

  const demoTimeouts = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearDemoTimeouts = () => {
    demoTimeouts.current.forEach(clearTimeout);
    demoTimeouts.current = [];
  };

  const sched = (fn: () => void, ms: number) => {
    const id = setTimeout(fn, ms);
    demoTimeouts.current.push(id);
  };

  const resetDemoState = () => {
    setDemoSarBanner(false);
    setDemoSlickOpacity(1);
    setDemoPipelinePhases(DEMO_PIPELINE_PHASES.map(p => ({ ...p, done: false, active: false })));
    setDemoShowOriginPulse(false);
    setDemoCameraTarget(null);
    setDemoShowTargetAcquired(false);
    setDemoEvidenceLine(0);
    setDemoShowPipelinePanel(false);
    setDemoShowSarTopBanner(false);
    setDemoOilTrail(null);
    setDemoRevealedLayers(undefined);
    setDemoSarPaused(false);
  };

  // ── High-fidelity multi-layer oil plume spreading behind vessel ────────
  const buildDemoOilSlick = (ratio: number): DemoOilTrailData => {
    const track = DEMO_INCIDENT.suspects[0].track;
    if (!track || track.length < 2 || ratio <= 0.012) {
      return { sheen: [], core: [], spine: [], blooms: [] };
    }

    const cumDist: number[] = [0];
    for (let i = 0; i < track.length - 1; i++) {
      const dlat = track[i + 1].lat - track[i].lat;
      const dlon = track[i + 1].lon - track[i].lon;
      cumDist.push(cumDist[cumDist.length - 1] + Math.sqrt(dlat * dlat + dlon * dlon));
    }
    const totalDist = cumDist[cumDist.length - 1];
    const targetDist = totalDist * Math.min(1, Math.max(0, ratio));

    const getPtAt = (dist: number): [number, number] => {
      if (dist <= 0) return [track[0].lat, track[0].lon];
      if (dist >= totalDist) return [track[track.length - 1].lat, track[track.length - 1].lon];
      for (let i = 0; i < cumDist.length - 1; i++) {
        if (cumDist[i] <= dist && dist <= cumDist[i + 1]) {
          const span = cumDist[i + 1] - cumDist[i];
          const f = span > 0 ? (dist - cumDist[i]) / span : 0;
          return [
            track[i].lat + f * (track[i + 1].lat - track[i].lat),
            track[i].lon + f * (track[i + 1].lon - track[i].lon),
          ];
        }
      }
      return [track[track.length - 1].lat, track[track.length - 1].lon];
    };

    const NUM_SAMPLES = 28;
    const pts: [number, number][] = [];
    for (let i = 0; i < NUM_SAMPLES; i++) {
      const d = targetDist * (i / (NUM_SAMPLES - 1));
      pts.push(getPtAt(d));
    }

    const coreLeft: [number, number][] = [];
    const coreRight: [number, number][] = [];
    const sheenLeft: [number, number][] = [];
    const sheenRight: [number, number][] = [];

    for (let i = 0; i < NUM_SAMPLES; i++) {
      const p = pts[i];
      const prev = pts[Math.max(0, i - 1)];
      const next = pts[Math.min(NUM_SAMPLES - 1, i + 1)];
      const dlat = next[0] - prev[0];
      const dlon = next[1] - prev[1];
      const len = Math.sqrt(dlat * dlat + dlon * dlon) || 1;
      const nlat = -dlon / len;
      const nlon = dlat / len;

      const tau = 1 - (i / (NUM_SAMPLES - 1)); // 1 at tail (oldest), 0 at ship
      // Core viscous width: starts at ~400m at stern, expands up to ~2.4 km!
      const wCore = 0.0035 + 0.019 * Math.pow(tau, 0.55) + 0.002 * Math.sin(i * 0.7);
      // Outer iridescent sheen width: expands up to ~4.2 km wide!
      const wSheen = wCore * 1.6 + 0.004;

      coreLeft.push([p[0] + nlat * wCore, p[1] + nlon * wCore]);
      coreRight.push([p[0] - nlat * wCore, p[1] - nlon * wCore]);
      sheenLeft.push([p[0] + nlat * wSheen, p[1] + nlon * wSheen]);
      sheenRight.push([p[0] - nlat * wSheen, p[1] - nlon * wSheen]);
    }

    const blooms: { center: [number, number]; radius: number; opacity: number }[] = [];
    if (ratio > 0.15) {
      const p1 = Math.min(1, (ratio - 0.15) / 0.85);
      blooms.push({
        center: [13.365, 80.475],
        radius: 900 + p1 * 2200,
        opacity: 0.5 + p1 * 0.25,
      });
    }
    if (ratio > 0.3) {
      const p2 = Math.min(1, (ratio - 0.3) / 0.7);
      blooms.push({
        center: [13.342, 80.452],
        radius: 1400 + p2 * 3200,
        opacity: 0.65 + p2 * 0.25,
      });
      blooms.push({
        center: [13.330, 80.446],
        radius: 1100 + p2 * 2500,
        opacity: 0.55 + p2 * 0.25,
      });
    }

    return {
      core: [...coreLeft, ...coreRight.reverse()],
      sheen: [...sheenLeft, ...sheenRight.reverse()],
      spine: pts,
      blooms,
    };
  };

  // ── PIPELINE PHASE REVEAL ───────────────────────────────────
  // Called after user provides / auto-simulates SAR image
  const runPipelineSequence = () => {
    setDemoSarPaused(false);
    setDemoShowPipelinePanel(true);
    setDemoSarBanner(true);
    setDemoShowSarTopBanner(true);

    // Phase timing base
    const BASE = 0;
    const PH = 1200; // ms per phase

    const phaseRevealMap: number[] = [1, 1 | 2, 1 | 2 | 4, 1 | 2 | 4 | 8, 1 | 2 | 4 | 8 | 16, 1 | 2 | 4 | 8 | 16];

    DEMO_PIPELINE_PHASES.forEach((_, i) => {
      sched(() => {
        setDemoPipelinePhases(prev => prev.map((p, idx) => ({
          ...p, active: idx === i, done: idx < i,
        })));
        setDemoRevealedLayers(phaseRevealMap[i]);
      }, BASE + i * PH);
    });
    // All phases done
    const allDoneAt = BASE + DEMO_PIPELINE_PHASES.length * PH;
    sched(() => {
      setDemoPipelinePhases(prev => prev.map(p => ({ ...p, active: false, done: true })));
      setDemoRevealedLayers(1 | 2 | 4 | 8 | 16);
    }, allDoneAt);

    // SAR banner hides, origin pulse + camera fly
    sched(() => {
      setDemoShowSarTopBanner(false);
      setDemoSarBanner(false);
      setDemoShowOriginPulse(true);
      setDemoCameraTarget([DEMO_INCIDENT.originHeatmap[0].lat, DEMO_INCIDENT.originHeatmap[0].lon]);
    }, allDoneAt + 800);

    // TARGET ACQUIRED overlay
    const taAt = allDoneAt + 2500;
    sched(() => {
      setDemoShowTargetAcquired(true);
      DEMO_INCIDENT.suspects[0].keyEvidence.forEach((_, i) => {
        sched(() => setDemoEvidenceLine(i + 1), taAt + i * 700);
      });
    }, taAt);

    // Switch to Attribution
    const attrAt = taAt + DEMO_INCIDENT.suspects[0].keyEvidence.length * 700 + 1500;
    sched(() => {
      setDemoShowTargetAcquired(false);
      setDemoShowPipelinePanel(false);
      setActiveTab('attribution');
      setSelectedVessel(DEMO_INCIDENT.suspects[0]);
    }, attrAt);

    // Switch to Reports
    sched(() => setActiveTab('reports'), attrAt + 4000);
  };

  const handleStartDemo = () => {
    if (demoActive) return;
    preDemo.current = { incidents, selectedIncident, selectedVessel, activeTab, timeOffsetRatio };
    resetDemoState();
    clearDemoTimeouts();

    setIncidents(prev => [DEMO_INCIDENT, ...prev.filter(i => i.id !== DEMO_INCIDENT.id)]);
    setSelectedIncident(DEMO_INCIDENT);
    setSelectedVessel(DEMO_INCIDENT.suspects[0]);
    setTimeOffsetRatio(0);
    setIsLiveBackend(true);
    setDemoActive(true);
    setDemoRevealedLayers(8); // show vessel markers only, no other layers yet
    setDemoCameraTarget([DEMO_INCIDENT.centerLat, DEMO_INCIDENT.centerLon]);
    setActiveTab('map');

    // ── PHASE 0: Vessel moves along track (0→1 over 8 seconds) ─────────────
    // High-fidelity multi-layer oil plume grows behind the ship as it moves
    let ratio = 0;
    const SHIP_DURATION = 8000; // 8 seconds
    const SHIP_TICKS = 80;
    const tickInterval = SHIP_DURATION / SHIP_TICKS;
    let tick = 0;
    const moveTick = () => {
      tick++;
      ratio = Math.min(1, tick / SHIP_TICKS);
      setTimeOffsetRatio(ratio);
      // Update high-fidelity oil plume
      setDemoOilTrail(buildDemoOilSlick(ratio));
      if (ratio < 1) {
        const id = setTimeout(moveTick, tickInterval);
        demoTimeouts.current.push(id);
      } else {
        // Ship has finished moving — pause for SAR input
        sched(() => setDemoSarPaused(true), 500);
      }
    };
    const id = setTimeout(moveTick, tickInterval);
    demoTimeouts.current.push(id);
  };

  const handleStopDemo = () => {
    clearDemoTimeouts();
    resetDemoState();
    setDemoActive(false);
    setIsLiveBackend(false);
    if (preDemo.current) {
      const snap = preDemo.current;
      setIncidents(snap.incidents);
      setSelectedIncident(snap.selectedIncident);
      setSelectedVessel(snap.selectedVessel);
      setActiveTab(snap.activeTab);
      setTimeOffsetRatio(snap.timeOffsetRatio);
      preDemo.current = null;
    }
  };

  // Stable refs for keyboard handler
  const demoActiveRef = useRef(demoActive);
  useEffect(() => { demoActiveRef.current = demoActive; }, [demoActive]);
  const handleStartDemoRef = useRef(handleStartDemo);
  useEffect(() => { handleStartDemoRef.current = handleStartDemo; });
  const handleStopDemoRef = useRef(handleStopDemo);
  useEffect(() => { handleStopDemoRef.current = handleStopDemo; });

  // Keyboard shortcut: 'D'
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === 'd' || e.key === 'D') {
        if (demoActiveRef.current) handleStopDemoRef.current();
        else handleStartDemoRef.current();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const toggleLayer = (k: string) =>
    setActiveLayers((p: any) => ({ ...p, [k]: !p[k] }));

  const handleIncidentIngested = (incident: IncidentCase) => {
    setIncidents((prev) => [incident, ...prev.filter((i) => i.id !== incident.id)]);
    setSelectedIncident(incident);
    setSelectedVessel(incident.suspects[0] || null);
    setTimeOffsetRatio(1.0);
    setIsLiveBackend(true);
    setActiveTab('dashboard');
  };

  const handleSelectIncident = (incident: IncidentCase) => {
    setSelectedIncident(incident);
    setSelectedVessel(incident.suspects[0] || null);
    setTimeOffsetRatio(1.0);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans print:h-auto print:overflow-visible print:block">
      <Navbar
        selectedIncident={selectedIncident}
        allIncidents={incidents}
        onSelectIncident={handleSelectIncident}
        isLiveBackend={isLiveBackend || wsConnected || backendReachable}
        wsConnected={wsConnected}
        backendReachable={backendReachable}
        pendingAlertCount={pendingAlertCount}
        onOpenAI={() => setActiveTab('ai')}
        onOpenAnalytics={() => setActiveTab('analytics')}
        onOpenReports={() => setActiveTab('reports')}
        onOpenIngest={() => setActiveTab('ingest')}
        onOpenSimulationVideo={() => setActiveTab('simulation-video')}
        onOpenCoastGuard={() => setActiveTab('cg-alerts')}
        isDemoActive={demoActive}
        onStartDemo={handleStartDemo}
        onStopDemo={handleStopDemo}
      />

      <TabBar
        active={activeTab}
        onChange={setActiveTab}
        pendingAlertCount={pendingAlertCount}
      />

      <div className="flex-1 relative overflow-hidden print:overflow-visible print:relative print:h-auto">
        {activeTab === 'dashboard' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <div className="max-w-[1700px] mx-auto space-y-5">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                <div className="lg:col-span-3">
                  <DashboardIngestPanel onGoFull={() => setActiveTab('ingest')} />
                </div>
                <div className="lg:col-span-6">
                  <div className="rounded-2xl border border-slate-800 bg-slate-900 overflow-hidden" style={{ height: '460px' }}>
                    <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between bg-gradient-to-r from-slate-900 to-cyan-950/20">
                      <div className="flex items-center space-x-2">
                        <div className="w-6 h-6 rounded-md bg-cyan-950 border border-cyan-700/60 flex items-center justify-center">
                          <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        </div>
                        <span className="text-[11px] font-bold text-slate-100 uppercase tracking-wider">Live Tactical Map</span>
                      </div>
                      <button onClick={() => setActiveTab('map')} className="text-[10px] text-cyan-400 hover:text-cyan-300 font-bold">
                        Full Map →
                      </button>
                    </div>
                    <div className="relative" style={{ height: 'calc(100% - 41px)' }}>
                      <HeroMap
                        incident={selectedIncident}
                        selectedVessel={selectedVessel}
                        onSelectVessel={setSelectedVessel}
                        timeOffsetRatio={timeOffsetRatio}
                        activeLayers={activeLayers}
                        showPipelines={showPipelines}
                      />
                    </div>
                  </div>
                </div>
                <div className="lg:col-span-3">
                  <DashboardValidationCase incident={selectedIncident} onGoAttribution={() => setActiveTab('attribution')} />
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <DashKPI icon={<Droplet className="w-5 h-5" />} color="rose" label="Slick Extent" value={selectedIncident.slickAreaKm2.toFixed(1)} unit="km²" sub={`~${selectedIncident.estimatedVolumeBarrels} bbls`} />
                <DashKPI icon={<Award className="w-5 h-5" />} color="rose" label="Top Attribution" value={`${selectedIncident.suspects[0]?.attributionScore ?? 0}`} unit="/100" sub={selectedIncident.suspects[0]?.name ?? 'No suspect'} />
                <DashKPI icon={<Ship className="w-5 h-5" />} color="cyan" label="Vessels Tracked" value={`${selectedIncident.suspects.length}`} unit="candidates" sub={`${selectedIncident.suspects.filter(s => s.isDarkVessel).length} dark vessels`} />
                <DashKPI icon={<Clock className="w-5 h-5" />} color="amber" label="Detection Age" value={`${selectedIncident.estimatedAgeHours}`} unit="hrs" sub={`Release ~${selectedIncident.estimatedReleaseWindow.hoursBeforeDetection}h prior`} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-cyan-800/50 bg-slate-900 p-5">
                  <div className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider mb-3">Live Environmental Telemetry</div>
                  <div className="grid grid-cols-2 gap-2">
                    <MiniStatBox label="Wind" value={`${selectedIncident.windSpeedKnots} kn`} sub={`@ ${selectedIncident.windDirectionDeg}°`} color="text-cyan-300" />
                    <MiniStatBox label="Current" value={`${selectedIncident.oceanCurrentSpeedKnots} kn`} sub={`@ ${selectedIncident.oceanCurrentDirDeg}°`} color="text-blue-300" />
                    <MiniStatBox label="Wave Ht" value={`${selectedIncident.waveHeightM} m`} sub="Significant" color="text-indigo-300" />
                    <MiniStatBox label="SST" value={`${selectedIncident.seaSurfaceTempC}°C`} sub="Surface" color="text-amber-300" />
                  </div>
                </div>

                <div className="rounded-2xl border border-emerald-800/50 bg-slate-900 p-5">
                  <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-3">Pipeline Status — 6 Phases</div>
                  <div className="space-y-1.5">
                    {['SAR Segmentation', 'FP Filtering', 'Drift Hindcast', 'AIS Correlation', 'Attribution', 'Dossier'].map((p, i) => (
                      <div key={p} className="flex items-center space-x-2 text-[11px]">
                        <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
                          <CheckCircle2 className="w-3 h-3 text-white" />
                        </div>
                        <span className="text-emerald-300 font-medium flex-1">Phase {i + 1} — {p}</span>
                        <span className="text-emerald-400 font-bold text-[10px] font-mono">PASS</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-rose-700/50 bg-slate-900 p-5 relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-[2px] bg-rose-500/70 animate-[scanline_2.5s_linear_infinite]" />
                  <div className="text-[10px] font-bold text-rose-400 uppercase tracking-wider mb-3">⚠ Dark Vessel Alerts</div>
                  <div className="space-y-2">
                    {selectedIncident.suspects.filter(s => s.isDarkVessel || s.behavioralAnomaly >= 90).slice(0, 3).map((v) => (
                      <div key={v.id} className="flex items-center justify-between text-[11px] bg-slate-800/70 border border-rose-800/40 rounded-lg px-3 py-2">
                        <span className="text-slate-200 font-semibold truncate max-w-[140px]">{v.name}</span>
                        <span className={`font-bold ${v.isDarkVessel ? 'text-rose-400' : 'text-amber-400'}`}>
                          {v.isDarkVessel ? 'AIS OFF' : 'SUSPICIOUS'}
                        </span>
                      </div>
                    ))}
                    {selectedIncident.suspects.filter(s => s.isDarkVessel || s.behavioralAnomaly >= 90).length === 0 && (
                      <div className="text-[11px] text-slate-400 italic py-2 text-center">No dark vessels detected.</div>
                    )}
                  </div>
                  <style>{`@keyframes scanline { 0% { top: 0%; } 100% { top: 100%; } }`}</style>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'map' && (
          <>
            <HeroMap
              incident={selectedIncident}
              selectedVessel={selectedVessel}
              onSelectVessel={setSelectedVessel}
              timeOffsetRatio={timeOffsetRatio}
              activeLayers={activeLayers}
              showPipelines={showPipelines}
              demoSlickOpacity={demoActive ? demoSlickOpacity : undefined}
              demoCameraTarget={demoCameraTarget}
              demoRevealedLayers={demoActive ? demoRevealedLayers : undefined}
              demoOilTrail={demoActive ? demoOilTrail : undefined}
            />
            {!demoActive && (
              <>
                <LayerControls
                  activeLayers={activeLayers}
                  toggleLayer={toggleLayer}
                  showPipelines={showPipelines}
                  setShowPipelines={setShowPipelines}
                />
                <StatusBar incident={selectedIncident} />
                <TimeMachineStrip
                  incident={selectedIncident}
                  timeOffsetRatio={timeOffsetRatio}
                  onChangeRatio={setTimeOffsetRatio}
                />
              </>
            )}
            {/* ── DEMO OVERLAYS ── */}
            {demoActive && <DemoWatermark />}
            {demoActive && demoShowSarTopBanner && <SarBanner />}
            {demoActive && demoShowPipelinePanel && (
              <DemoPipelinePanel
                phases={demoPipelinePhases}
                sarBanner={demoSarBanner}
                showOriginPulse={demoShowOriginPulse}
              />
            )}
            {/* SAR Pause Modal — appears after ship finishes moving */}
            {demoActive && demoSarPaused && (
              <DemoSarModal onProceed={runPipelineSequence} />
            )}
            {demoActive && demoShowTargetAcquired && (
              <DemoTargetAcquired
                vessel={DEMO_INCIDENT.suspects[0]}
                evidenceLine={demoEvidenceLine}
              />
            )}
            {/* Playback progress bar (visible during ship animation phase) */}
            {demoActive && !demoSarPaused && !demoShowPipelinePanel && (
              <div
                className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1001] w-[620px] max-w-[92vw] rounded-2xl p-4 shadow-2xl backdrop-blur-xl no-print"
                style={{
                  background: 'rgba(2, 6, 23, 0.96)',
                  border: '1.5px solid rgba(244, 63, 94, 0.65)',
                  boxShadow: '0 0 50px rgba(0,0,0,0.9), 0 0 25px rgba(244,63,94,0.3)',
                }}
              >
                <div className="flex items-center space-x-3.5 mb-2.5">
                  <div className="w-10 h-10 rounded-xl bg-rose-600/30 border border-rose-500 flex items-center justify-center flex-shrink-0">
                    <Ship className="w-5 h-5 text-rose-400 animate-pulse" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-black text-white font-mono tracking-wide flex items-center space-x-2">
                        <span>MV SARASWATI STAR · LEAK IN PROGRESS</span>
                        <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
                      </div>
                      <span className="text-xs font-mono text-amber-300 font-bold">
                        {timeOffsetRatio >= 0.99 ? 'DISCHARGE FINISHED' : `T-${((1 - timeOffsetRatio) * DEMO_INCIDENT.estimatedReleaseWindow.hoursBeforeDetection).toFixed(1)}h RELEASE`}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-300 font-mono mt-0.5">
                      Crude Oil Venting · Speed: {(11.2 * (1 - timeOffsetRatio * 0.75)).toFixed(1)} kn · Est. Discharged: ~{Math.round(timeOffsetRatio * 1250)} bbl
                    </div>
                  </div>
                </div>
                <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden p-0.5 border border-slate-700/80">
                  <div
                    className="h-full bg-gradient-to-r from-amber-400 via-rose-500 to-rose-600 rounded-full transition-all duration-150 shadow-[0_0_12px_rgba(244,63,94,0.6)]"
                    style={{ width: `${Math.max(2, timeOffsetRatio * 100)}%` }}
                  />
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'simulation-video' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <SimulationVideoStudio
              incident={selectedIncident}
              allIncidents={incidents}
              onSelectIncident={setSelectedIncident}
            />
          </div>
        )}

        {activeTab === 'cg-alerts' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <CoastGuardAlertPanel
              alerts={cgAlerts}
              selectedAlertId={selectedAlertId}
              onSelectAlert={setSelectedAlertId}
              onAcknowledge={handleAckCgAlert}
              onTriggerTestAlert={handleTriggerTestAlert}
              stations={cgStations}
              backendConnected={wsConnected || backendReachable}
            />
          </div>
        )}

        {activeTab === 'attribution' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <AttributionFullPage
              incident={selectedIncident}
              selectedVessel={selectedVessel}
              onSelectVessel={setSelectedVessel}
            />
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="absolute inset-0 overflow-hidden">
            <AIConsoleInline incident={selectedIncident} />
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <AnalyticsInline incident={selectedIncident} />
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6 print:overflow-visible print:static print:p-0 print:bg-white">
            <ReportsInline incident={selectedIncident} />
          </div>
        )}

        {activeTab === 'ingest' && (
          <div className="absolute inset-0 overflow-y-auto bg-slate-950 p-6">
            <IngestInline onIngested={handleIncidentIngested} />
          </div>
        )}
      </div>

      <LiveEventTicker incident={selectedIncident} />
    </div>
  );
};

const DashKPI: React.FC<{ icon: React.ReactNode; color: string; label: string; value: string; unit: string; sub: string }> = ({ icon, color, label, value, unit, sub }) => {
  const colorMap: Record<string, string> = {
    rose: 'from-rose-950/40 to-slate-900 border-rose-700/50 text-rose-400',
    cyan: 'from-cyan-950/40 to-slate-900 border-cyan-700/50 text-cyan-400',
    amber: 'from-amber-950/40 to-slate-900 border-amber-700/50 text-amber-400',
  };
  return (
    <div className={`rounded-2xl border bg-gradient-to-br p-5 ${colorMap[color]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">{label}</span>
        <span className="opacity-80">{icon}</span>
      </div>
      <div className="flex items-baseline space-x-2">
        <span className="text-4xl font-extrabold text-white">{value}</span>
        <span className="text-sm text-slate-400">{unit}</span>
      </div>
      <div className="text-xs text-slate-400 mt-2 truncate">{sub}</div>
    </div>
  );
};

const MiniStatBox: React.FC<{ label: string; value: string; sub: string; color: string }> = ({ label, value, sub, color }) => (
  <div className="bg-slate-800/60 rounded-lg p-2.5 border border-slate-700/60">
    <div className="text-[9px] text-slate-400 uppercase font-bold">{label}</div>
    <div className={`text-base font-bold mt-0.5 ${color}`}>{value}</div>
    <div className="text-[9px] text-slate-500">{sub}</div>
  </div>
);

const DashboardIngestPanel: React.FC<{ onGoFull: () => void }> = ({ onGoFull }) => {
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.type.startsWith('image/')) return;
    setFile(f);
  };

  return (
    <div className="rounded-2xl border border-cyan-700/60 bg-gradient-to-br from-cyan-950/30 via-slate-900 to-slate-900 p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/60 flex items-center justify-center">
            <Satellite className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Quick Ingest</span>
        </div>
        <button onClick={onGoFull} className="text-[10px] text-cyan-400 hover:text-cyan-300 font-bold">Full UI →</button>
      </div>

      <div
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all h-[180px] flex flex-col items-center justify-center ${
          drag ? 'border-cyan-400 bg-cyan-950/40' : file ? 'border-emerald-500 bg-emerald-950/30' : 'border-slate-700 hover:border-cyan-600 hover:bg-slate-800/60'
        }`}>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
        {file ? (
          <>
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
            <div className="text-xs font-bold text-emerald-300 truncate max-w-[180px]">{file.name}</div>
            <div className="text-[10px] text-emerald-400/70 mt-1 font-mono">{(file.size / 1024).toFixed(1)} KB</div>
          </>
        ) : (
          <>
            <Upload className="w-8 h-8 text-slate-500 mb-2" />
            <div className="text-xs font-bold text-slate-300">Drop SAR image</div>
            <div className="text-[10px] text-slate-500 mt-1">or click to browse</div>
          </>
        )}
      </div>

      <div className="mt-3 space-y-2">
        <div className="text-[10px] text-slate-400 uppercase font-bold">Target Sector</div>
        <select className="w-full bg-slate-800 border border-slate-700 text-slate-100 text-[11px] rounded-lg px-2 py-1.5 focus:outline-none focus:border-cyan-500">
          {PRESET_SECTORS.map((s, i) => <option key={i} value={i} className="bg-slate-900">{s.label}</option>)}
        </select>
      </div>

      <button onClick={onGoFull}
        className="w-full mt-3 flex items-center justify-center space-x-2 px-4 py-2.5 font-bold text-xs rounded-xl transition-all bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-lg active:scale-[0.98]">
        <Zap className="w-3.5 h-3.5 text-yellow-300" />
        <span>Run Forensic Pipeline</span>
      </button>
    </div>
  );
};

const DashboardValidationCase: React.FC<{ incident: IncidentCase; onGoAttribution: () => void }> = ({ incident, onGoAttribution }) => {
  const top = incident.suspects[0];
  return (
    <div className="rounded-2xl border border-rose-700/60 bg-gradient-to-br from-rose-950/30 via-slate-900 to-slate-900 p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/60 flex items-center justify-center">
            <FileCheck className="w-4 h-4 text-rose-400" />
          </div>
          <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">Validation Case</span>
        </div>
        <button onClick={onGoAttribution} className="text-[10px] text-rose-400 hover:text-rose-300 font-bold">Full →</button>
      </div>

      <div className="mb-3 pb-3 border-b border-slate-700/60">
        <div className="text-[9px] text-slate-500 uppercase font-bold mb-1">Case Reference</div>
        <div className="text-xs font-bold text-slate-100">{incident.title}</div>
        <div className="text-[10px] text-slate-400 mt-0.5">{incident.regionName}</div>
      </div>

      {top && (
        <>
          <div className="flex items-center space-x-2.5 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-rose-600 to-amber-600 flex items-center justify-center flex-shrink-0">
              <Ship className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate">{top.name}</div>
              <div className="text-[9px] text-slate-400 font-mono">MMSI {top.mmsi}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="bg-slate-900/70 rounded-lg p-2 text-center border border-rose-700/30">
              <div className="text-[9px] text-slate-400 uppercase font-bold">Score</div>
              <div className="text-2xl font-extrabold text-rose-400 leading-none">{top.attributionScore}</div>
            </div>
            <div className="bg-slate-900/70 rounded-lg p-2 text-center border border-emerald-700/30">
              <div className="text-[9px] text-slate-400 uppercase font-bold">Grade</div>
              <div className="text-sm font-bold text-emerald-400 mt-1">{top.evidenceGrade}</div>
            </div>
          </div>

          <div className="space-y-1.5 flex-1">
            <div className="text-[9px] text-slate-500 uppercase font-bold mb-1.5">Evidence Summary</div>
            {top.keyEvidence.slice(0, 3).map((ev, i) => (
              <div key={i} className="flex items-start space-x-1.5 text-[10px] text-slate-300 leading-tight">
                <CheckCircle2 className="w-3 h-3 text-emerald-400 flex-shrink-0 mt-0.5" />
                <span className="line-clamp-2">{ev}</span>
              </div>
            ))}
          </div>

          <div className="mt-3 pt-3 border-t border-slate-700/60">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-slate-500">Distance</span>
              <span className="text-slate-100 font-bold">{top.distanceToOriginKm} km</span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono mt-1">
              <span className="text-slate-500">Time Delta</span>
              <span className="text-slate-100 font-bold">{top.timeDiffMinutes} min</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default App;