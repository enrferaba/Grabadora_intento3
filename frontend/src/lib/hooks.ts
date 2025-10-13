import { useCallback, useEffect, useState } from "react";
import {
  AccountProfile,
  AppConfig,
  QualityProfile,
  fetchAppConfig,
  fetchProfiles,
  getCachedAccountProfiles,
  getCachedConfig,
  getCachedQualityProfiles,
  hasConfigCache,
  hasProfileCache,
} from "./api";

interface UseQualityProfilesResult {
  profiles: QualityProfile[];
  accountProfiles: AccountProfile[];
  loading: boolean;
  error: string | null;
  refresh: (force?: boolean) => Promise<void>;
}

export function useQualityProfiles(): UseQualityProfilesResult {
  const [profiles, setProfiles] = useState<QualityProfile[]>(() => getCachedQualityProfiles());
  const [accountProfiles, setAccountProfiles] = useState<AccountProfile[]>(() => getCachedAccountProfiles());
  const [loading, setLoading] = useState<boolean>(() => !hasProfileCache());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    try {
      const data = await fetchProfiles(force);
      setProfiles(data.quality_profiles);
      setAccountProfiles(data.account_profiles);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudieron cargar los perfiles";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasProfileCache()) {
      void load();
    }
  }, [load]);

  const refresh = useCallback(
    async (force = true) => {
      await load(force);
    },
    [load],
  );

  return { profiles, accountProfiles, loading, error, refresh };
}

interface UseAppConfigResult {
  config: AppConfig | null;
  loading: boolean;
  error: string | null;
  refresh: (force?: boolean) => Promise<void>;
}

export function useAppConfig(): UseAppConfigResult {
  const [config, setConfig] = useState<AppConfig | null>(() => getCachedConfig());
  const [loading, setLoading] = useState<boolean>(() => !hasConfigCache());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    try {
      const data = await fetchAppConfig(force);
      setConfig(data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo cargar la configuración";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasConfigCache()) {
      void load();
    }
  }, [load]);

  const refresh = useCallback(
    async (force = true) => {
      await load(force);
    },
    [load],
  );

  return { config, loading, error, refresh };
}
