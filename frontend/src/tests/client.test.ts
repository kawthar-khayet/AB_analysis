import { describe, expect, it, vi } from "vitest";
import { ApiError, request } from "../api/client";

function mockFetch(body: BodyInit, status: number, headers: Record<string, string>) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status, headers }));
}

describe("request", () => {
  it("préfixe /api/v1 et envoie du JSON", async () => {
    const spy = mockFetch(JSON.stringify({ status: "ok" }), 200, { "content-type": "application/json" });

    const data = await request<{ status: string }>("/health", { method: "POST", body: "{}" });

    expect(data).toEqual({ status: "ok" });
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/health");
    expect(new Headers(init!.headers).get("Content-Type")).toBe("application/json");
  });

  it.each([
    ["application/pdf", "attachment; filename=\"rapport.pdf\""],
    ["application/json", "attachment; filename=\"resultat.json\""],
    ["text/csv; charset=utf-8", "attachment; filename=\"resultat.csv\""],
  ])("renvoie un Blob pour un fichier exporté (%s)", async (contentType, disposition) => {
    mockFetch("contenu", 200, { "content-type": contentType, "content-disposition": disposition });

    const data = await request<Blob>("/exports/x", { method: "POST" });

    // Pas de `toBeInstanceOf(Blob)` : selon la version de Node, `fetch` crée un Blob natif
    // de Node, différent de la classe Blob de jsdom. On vérifie donc la nature de l'objet.
    expect(Object.prototype.toString.call(data)).toBe("[object Blob]");
    expect(data.size).toBe("contenu".length);
  });

  it("transforme une erreur structurée de l'API en ApiError", async () => {
    mockFetch(
      JSON.stringify({ code: "UNKNOWN_METHOD", category: "validation", message: "Méthode inconnue" }),
      422,
      { "content-type": "application/json" },
    );

    const error = (await request("/analyses").catch((e) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe("UNKNOWN_METHOD");
    expect(error.message).toBe("Méthode inconnue");
  });
});
