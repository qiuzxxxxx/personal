import api, { requestPath } from "./client";

export interface SiteAboutLink {
  label: string;
  url: string;
}

export interface SiteAboutContent {
  site_name: string;
  tagline: string;
  intro: string;
  features: string;
  developer: string;
  contact: string;
  app_version: string;
  guide: string;
  links: SiteAboutLink[];
  updated_at: string | null;
}

export async function fetchSiteAbout(): Promise<SiteAboutContent> {
  const { data } = await api.get<SiteAboutContent>(requestPath("/about/"));
  return data;
}

export async function saveSiteAbout(payload: SiteAboutContent): Promise<SiteAboutContent> {
  const { data } = await api.put<SiteAboutContent>(requestPath("/about/"), payload);
  return data;
}
