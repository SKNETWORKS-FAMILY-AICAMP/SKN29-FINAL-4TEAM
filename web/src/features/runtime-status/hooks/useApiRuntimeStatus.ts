import { useEffect, useState } from "react";

import {
  probeApiRuntime,
  type ApiRuntimeProbe,
} from "../api/runtimeStatusApi";

export type ApiRuntimeState =
  | { status: "checking"; probe: null }
  | { status: "connected"; probe: ApiRuntimeProbe }
  | { status: "unavailable"; probe: null };

const POLL_INTERVAL_MS = 15_000;

export default function useApiRuntimeStatus(): ApiRuntimeState {
  const [state, setState] = useState<ApiRuntimeState>({
    status: "checking",
    probe: null,
  });

  useEffect(() => {
    let active = true;
    let controller: AbortController | null = null;

    const check = async () => {
      controller?.abort();
      controller = new AbortController();

      try {
        const probe = await probeApiRuntime(controller.signal);
        if (active) setState({ status: "connected", probe });
      } catch (error) {
        if (active && !(error instanceof DOMException && error.name === "AbortError")) {
          setState({ status: "unavailable", probe: null });
        }
      }
    };

    void check();
    const pollId = window.setInterval(() => void check(), POLL_INTERVAL_MS);

    return () => {
      active = false;
      controller?.abort();
      window.clearInterval(pollId);
    };
  }, []);

  return state;
}
