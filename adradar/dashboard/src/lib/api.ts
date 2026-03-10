// src/lib/api.ts

export interface Lead {
  id: string; // Airtable ID
  brand: string;
  website: string;
  score: number;
  tier: "HOT" | "WARM" | "COLD";
  signals: {
    s1: number;
    s2: number;
    s3: number;
    s4: number;
    s5: number;
  };
  daysRunning: number;
  numAds: number;
  estSpend: string;
  adCopy: string;
  contact: {
    name: string;
    title: string;
    email: string | null;
    confirmed: boolean;
  };
  pushedToInstantly: boolean;
  dateAdded: string;
}

// Ensure you run the python FastAPI backend on port 8000
const API_BASE = "http://localhost:8000/api";

export async function fetchLiveLeads(): Promise<Lead[]> {
  try {
    const res = await fetch(`${API_BASE}/leads`);
    if (!res.ok) throw new Error("Failed to fetch leads");
    const data = await res.json();
    return data.leads as Lead[];
  } catch (error) {
    console.error("Error fetching leads from Python backend:", error);
    return []; // fallback empty
  }
}

export async function triggerPipelineRun(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/pipeline/run`, { method: "POST" });
    return res.ok;
  } catch (error) {
    console.error("Error triggering pipeline:", error);
    return false;
  }
}

export interface HealthStatus {
  status: "online" | "offline";
  airtable: string;
  timestamp: string;
}

export async function fetchHealthStatus(): Promise<HealthStatus> {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error("Not OK");
    const data = await res.json();
    return { status: "online", airtable: data.airtable, timestamp: data.timestamp };
  } catch {
    return { status: "offline", airtable: "disconnected", timestamp: new Date().toISOString() };
  }
}

export interface PipelineRun {
  date: string;
  scraped: string | number;
  filtered: string | number;
  enriched: string | number;
  hot: string | number;
  warm: string | number;
  cold: string | number;
  pushed: string | number;
  duration: string;
  current?: boolean;
}

export async function fetchPipelineHistory(): Promise<PipelineRun[]> {
  try {
    const res = await fetch(`${API_BASE}/pipeline/history`);
    if (!res.ok) throw new Error("Failed to fetch history");
    const data = await res.json();
    return data.history || [];
  } catch (error) {
    console.error("Error fetching pipeline history:", error);
    return [];
  }
}
