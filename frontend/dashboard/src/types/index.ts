/**
 * Payodhi Full Pipeline & Phase 7 Coast Guard Alert Contracts
 */

export interface CoastGuardAlert {
  id: string;
  stationId: string;
  stationName: string;
  stationDistanceKm: number;
  backupStations: string[];
  severity: 'MODERATE' | 'HIGH';
  confidence: number;
  topSuspect?: string | null;
  interceptionCount: number;
  nearestVessels: string[];
  etaHours: number;
  createdAt: string;
  ackedBy?: string | null;
  ackedAt?: string | null;
  smsStatus?: string;
  smsReason?: string | null;
}

export interface CandidateAttribution {
  vessel_id: string;
  vessel_name: string;
  mmsi: string;
  vessel_type?: string;
  total_score: number;
  confidence_pct: number;
  p_value: number;
  stability_index: number;
  capacity_veto: boolean;
  verdict: 'PROSECUTABLE' | 'PERSON_OF_INTEREST' | 'INSUFFICIENT_EVIDENCE';
  cpa_distance_km?: number;
  tcpa_hours?: number;
  loitering_detected?: boolean;
  dark_vessel_flag?: boolean;
  evidence_bullets?: string[];
}

export interface PipelineResult {
  scene_id: string;
  status: string;
  spill?: {
    id: string;
    area_sq_km: number;
    confidence_score: number;
    status: string;
    review_notes?: string;
  };
  drift?: {
    drift_run_id: string;
    origin_latitude: number;
    origin_longitude: number;
    time_window_hours: number;
  };
  ais?: {
    correlated_vessels_count: number;
    dark_vessels_detected: number;
  };
  attribution?: {
    candidates: CandidateAttribution[];
    top_suspect?: CandidateAttribution;
  };
  response?: {
    alert_id: string;
    primary_station: string;
    station_distance_km: number;
    eta_hours: number;
    intercept_vessels_count: number;
    status: string;
  };
}

export interface IncidentCase {
  id: string;
  title: string;
  coastGuardAlert?: CoastGuardAlert | null;
}
