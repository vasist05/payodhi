/**
 * Phase 8 types — Coast Guard alert contract.
 *
 * This is the shape the backend adapter emits (snake_case → camelCase)
 * and the panel consumes. Kept minimal on purpose: when this dashboard
 * merges into the full `vasist` dashboard, only CoastGuardAlert and the
 * `coastGuardAlert` field on IncidentCase need to survive.
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

/**
 * Minimal IncidentCase — only the Phase 8 surface.
 * The full dashboard has a much larger IncidentCase; this is the subset
 * the Coast Guard panel needs.
 */
export interface IncidentCase {
  id: string;
  title: string;
  coastGuardAlert?: CoastGuardAlert | null;
}
