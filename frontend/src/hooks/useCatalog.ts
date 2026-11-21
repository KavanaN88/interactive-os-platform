import { useEffect, useState } from "react";
import { get } from "../lib/api";
import type { CatalogItem } from "../types";

export function useCatalog(path: string) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { get<CatalogItem[]>(path).then(setItems).catch((e: Error) => setError(e.message)); }, [path]);
  return { items, error };
}
