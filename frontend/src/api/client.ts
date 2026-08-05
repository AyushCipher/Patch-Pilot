import axios from "axios";
import type { BugBankEntry, BugDetailResponse, HarnessReport, RunStatus, RunSummary, TraceEvent } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({ baseURL: API_BASE_URL });

export function wsBaseUrl(): string {
  return API_BASE_URL.replace(/^http/, "ws");
}

export async function listBugs(): Promise<BugBankEntry[]> {
  const { data } = await apiClient.get<BugBankEntry[]>("/api/bugs");
  return data;
}

export async function startRunAgainstBug(bugId: string): Promise<RunSummary> {
  const form = new FormData();
  form.append("bug_id", bugId);
  const { data } = await apiClient.post<RunSummary>("/api/runs", form);
  return data;
}

export async function startRunFromUpload(file: File): Promise<RunSummary> {
  const form = new FormData();
  form.append("repo_zip", file);
  const { data } = await apiClient.post<RunSummary>("/api/runs", form);
  return data;
}

export async function getRunStatus(runId: string): Promise<RunStatus> {
  const { data } = await apiClient.get<RunStatus>(`/api/runs/${runId}`);
  return data;
}

export async function getRunTrace(runId: string): Promise<TraceEvent[]> {
  const { data } = await apiClient.get<TraceEvent[]>(`/api/runs/${runId}/trace`);
  return data;
}

export async function getEvalReport(): Promise<HarnessReport> {
  const { data } = await apiClient.get<HarnessReport>("/api/eval/report");
  return data;
}

export async function getBugDetail(bugId: string): Promise<BugDetailResponse> {
  const { data } = await apiClient.get<BugDetailResponse>(`/api/eval/report/${bugId}`);
  return data;
}
