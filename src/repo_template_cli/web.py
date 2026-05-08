from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid
import webbrowser

from .cli import example_config


HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>repo-template</title>
  <style>
    :root {
      --bg: #f4f4f7;
      --panel: rgba(255, 255, 255, 0.84);
      --panel-solid: #ffffff;
      --control: rgba(255, 255, 255, 0.92);
      --control-hover: #f3f3f6;
      --line: #d7d7df;
      --line-soft: rgba(0, 0, 0, 0.07);
      --text: #1d1d1f;
      --muted: #6e6e73;
      --muted-soft: #8a8a91;
      --blue: #0071e3;
      --blue-dark: #005bbd;
      --blue-soft: rgba(0, 113, 227, 0.12);
      --green: #148a45;
      --orange: #b06000;
      --red: #c62929;
      --shadow: 0 18px 44px rgba(23, 23, 26, 0.09), 0 1px 2px rgba(23, 23, 26, 0.06);
      --shadow-soft: 0 8px 24px rgba(23, 23, 26, 0.07), 0 1px 2px rgba(23, 23, 26, 0.05);
    }

    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, #fbfbfd 0%, #f5f5f8 38%, #eceef3 100%);
      letter-spacing: 0;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }

    button, input, textarea, select {
      font: inherit;
      letter-spacing: 0;
    }

    button {
      border: 0;
      border-radius: 8px;
      cursor: pointer;
      min-height: 36px;
      padding: 0 14px;
      color: var(--text);
      background: linear-gradient(180deg, #ffffff 0%, #f0f0f3 100%);
      border: 1px solid rgba(0, 0, 0, 0.08);
      box-shadow: 0 1px 1px rgba(0, 0, 0, 0.04);
      font-weight: 600;
      transition: background 150ms ease, color 150ms ease, transform 150ms ease, box-shadow 150ms ease;
    }

    button:hover {
      background: linear-gradient(180deg, #ffffff 0%, #e8e8ed 100%);
      box-shadow: 0 3px 10px rgba(0, 0, 0, 0.07);
    }
    button:active { transform: translateY(1px); }
    button.primary {
      color: white;
      background: linear-gradient(180deg, #1683f5 0%, var(--blue) 100%);
      border-color: rgba(0, 87, 173, 0.35);
      box-shadow: 0 8px 18px rgba(0, 113, 227, 0.22), 0 1px 1px rgba(0, 0, 0, 0.12);
    }
    button.primary:hover {
      background: linear-gradient(180deg, #0878ea 0%, var(--blue-dark) 100%);
      box-shadow: 0 10px 24px rgba(0, 113, 227, 0.26), 0 1px 1px rgba(0, 0, 0, 0.12);
    }
    button.danger {
      color: white;
      background: linear-gradient(180deg, #db3b3b 0%, var(--red) 100%);
      border-color: rgba(160, 20, 20, 0.32);
    }
    button.ghost {
      background: rgba(255, 255, 255, 0.36);
      border: 1px solid var(--line);
    }
    button.icon {
      width: 36px;
      padding: 0;
      font-weight: 700;
    }

    button:focus-visible {
      outline: none;
      box-shadow: 0 0 0 4px var(--blue-soft), 0 3px 10px rgba(0, 0, 0, 0.08);
    }

    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--control);
      color: var(--text);
      outline: none;
      padding: 10px 11px;
      min-height: 40px;
      box-shadow: inset 0 1px 1px rgba(0, 0, 0, 0.035), 0 1px 0 rgba(255, 255, 255, 0.72);
      transition: border-color 150ms ease, box-shadow 150ms ease, background 150ms ease;
    }

    input[readonly] {
      color: var(--muted);
      background: #f2f2f5;
    }

    textarea {
      min-height: 78px;
      resize: vertical;
      font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
      font-size: 13px;
      line-height: 1.45;
    }

    input:focus, textarea:focus, select:focus {
      border-color: var(--blue);
      background: #ffffff;
      box-shadow: 0 0 0 4px var(--blue-soft), inset 0 1px 1px rgba(0, 0, 0, 0.025);
    }

    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      line-height: 1.3;
    }

    .app {
      display: grid;
      grid-template-columns: 316px minmax(0, 1fr);
      min-height: 100vh;
    }

    aside {
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
      padding: 24px;
      background: rgba(252, 252, 255, 0.72);
      border-right: 1px solid var(--line-soft);
      backdrop-filter: blur(22px);
      box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.74);
    }

    main {
      min-width: 0;
      padding: 32px 48px 48px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 26px;
      font-weight: 700;
      font-size: 18px;
      color: #171719;
    }

    .brand-mark {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 8px;
      color: white;
      background: linear-gradient(145deg, #111827 0%, #215fbd 52%, #00a3a3 100%);
      box-shadow: 0 10px 24px rgba(0, 83, 181, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.22);
      font-size: 13px;
    }

    .side-block {
      display: grid;
      gap: 10px;
      margin-bottom: 22px;
    }

    .side-title {
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .button-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .path-picker {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 36px;
      gap: 8px;
      align-items: center;
    }

    .path-picker input {
      min-width: 0;
    }

    .repo-picker {
      grid-template-columns: minmax(0, 1fr) 72px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      margin-bottom: 24px;
    }

    h1 {
      margin: 0;
      font-size: 40px;
      line-height: 1.06;
      font-weight: 760;
      max-width: 780px;
    }

    .file-state {
      flex: 0 0 auto;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 9px 11px;
      background: rgba(255, 255, 255, 0.68);
      color: var(--muted);
      font-size: 12px;
      max-width: 420px;
      overflow-wrap: anywhere;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
    }

    .topbar .file-state {
      justify-self: end;
    }

    .tabs {
      display: inline-flex;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: rgba(232, 232, 237, 0.72);
      margin-bottom: 24px;
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 0 rgba(255, 255, 255, 0.78);
    }

    .tab {
      min-height: 34px;
      background: transparent;
      color: var(--muted);
    }

    .tab.active {
      background: white;
      color: var(--text);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.10), 0 1px 1px rgba(0, 0, 0, 0.05);
    }

    .panel {
      display: none;
    }

    .panel.active {
      display: grid;
      gap: 22px;
    }

    .surface {
      position: relative;
      z-index: 1;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.92) 0%, var(--panel) 100%);
      box-shadow: var(--shadow);
      overflow: visible;
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
      backdrop-filter: blur(18px);
    }

    .surface:hover {
      border-color: rgba(0, 0, 0, 0.10);
      box-shadow: 0 22px 58px rgba(23, 23, 26, 0.10), 0 1px 2px rgba(23, 23, 26, 0.06);
    }

    .surface:focus-within {
      z-index: 20;
    }

    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 15px 18px;
      border-bottom: 1px solid var(--line-soft);
      background: rgba(250, 250, 252, 0.72);
    }

    .section-head h2 {
      margin: 0;
      font-size: 17px;
      line-height: 1.2;
      font-weight: 720;
    }

    .section-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .section-body {
      padding: 18px;
      display: grid;
      gap: 18px;
    }

    .grid {
      display: grid;
      gap: 15px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid .wide { grid-column: 1 / -1; }

    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px;
      padding: 4px;
      border-radius: 8px;
      background: rgba(232, 232, 237, 0.86);
      border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .segmented button {
      background: transparent;
      color: var(--muted);
    }

    .segmented button.active {
      background: #ffffff;
      color: var(--text);
      box-shadow: 0 4px 11px rgba(0, 0, 0, 0.10), 0 1px 1px rgba(0, 0, 0, 0.05);
    }

    .list {
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      overflow: visible;
      background: rgba(255, 255, 255, 0.78);
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
    }

    .list-row {
      position: relative;
      display: grid;
      gap: 12px;
      padding: 15px;
      border-bottom: 1px solid var(--line-soft);
      transition: background 160ms ease;
    }

    .list-row:hover { background: rgba(248, 248, 252, 0.86); }

    .list-row:last-child { border-bottom: 0; }

    .row-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .value-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      padding: 10px 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: linear-gradient(180deg, #fbfbfd 0%, #f2f2f6 100%);
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.74);
    }

    .repo-value-list {
      display: grid;
      gap: 10px;
    }

    .repo-scoped {
      display: grid;
      gap: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--line-soft);
    }

    .repo-scoped-section {
      display: grid;
      gap: 10px;
    }

    .repo-scoped-head {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .repo-scoped-items {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .repo-scoped-item {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    .field-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .suggest-wrap {
      position: relative;
      display: grid;
      gap: 6px;
    }

    .repo-field {
      display: grid;
      gap: 6px;
    }

    .suggestions {
      position: absolute;
      z-index: 80;
      top: calc(100% + 6px);
      left: 0;
      right: 0;
      max-height: 240px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      box-shadow: 0 18px 42px rgba(23, 23, 26, 0.16), 0 2px 8px rgba(23, 23, 26, 0.08);
      padding: 4px;
    }

    .suggestions:empty,
    .suggestions.hidden {
      display: none;
    }

    .suggestion {
      width: 100%;
      min-height: 34px;
      display: grid;
      gap: 2px;
      padding: 8px 10px;
      border-radius: 6px;
      background: white;
      text-align: left;
      box-shadow: none;
    }

    .suggestion:hover { background: #f2f7ff; }
    .suggestion strong { font-size: 13px; }
    .suggestion span { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }

    .checks {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }

    .check {
      display: flex;
      grid-template-columns: none;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-size: 13px;
      font-weight: 500;
    }

    .check input {
      width: 16px;
      height: 16px;
      min-height: 16px;
      padding: 0;
      accent-color: var(--blue);
    }

    .empty {
      padding: 22px;
      color: var(--muted);
      font-size: 14px;
      text-align: center;
      background: rgba(248, 248, 251, 0.78);
    }

    .json-editor {
      min-height: 620px;
    }

    .job-layout {
      display: grid;
      grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
      gap: 18px;
    }

    .jobs-list {
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.78);
      overflow: hidden;
    }

    .job-item {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 5px 10px;
      border-radius: 0;
      border-bottom: 1px solid var(--line-soft);
      background: rgba(255, 255, 255, 0.72);
      padding: 12px;
      text-align: left;
      box-shadow: none;
    }

    .job-item:last-child { border-bottom: 0; }
    .job-item.active { background: #eef6ff; }
    .job-name { font-weight: 700; }
    .job-meta { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }

    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
      background: #eeeeef;
      color: var(--muted);
      white-space: nowrap;
    }

    .badge.running { color: var(--blue); background: rgba(0, 113, 227, 0.10); }
    .badge.done { color: var(--green); background: rgba(20, 138, 69, 0.10); }
    .badge.failed { color: var(--red); background: rgba(198, 41, 41, 0.10); }
    .badge.queued { color: var(--orange); background: rgba(176, 96, 0, 0.10); }

    pre {
      margin: 0;
      min-height: 520px;
      max-height: 68vh;
      overflow: auto;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #111827;
      color: #dbe7ff;
      padding: 16px;
      font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }

    .toast {
      position: fixed;
      right: 20px;
      bottom: 20px;
      max-width: min(420px, calc(100vw - 40px));
      padding: 12px 14px;
      border-radius: 8px;
      color: white;
      background: rgba(29, 29, 31, 0.94);
      box-shadow: 0 18px 44px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.12);
      opacity: 0;
      transform: translateY(8px);
      transition: 160ms ease;
      pointer-events: none;
      z-index: 20;
    }

    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }

    @media (max-width: 940px) {
      .app { grid-template-columns: 1fr; }
      aside {
        position: relative;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line-soft);
      }
      .topbar { gap: 12px; }
      .file-state { max-width: 100%; }
      .grid, .grid.three, .job-layout, .repo-scoped-items { grid-template-columns: 1fr; }
      main { padding: 24px 18px 36px; }
      h1 { font-size: 34px; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        transition-duration: 1ms !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <div class="brand"><span class="brand-mark">rt</span><span>repo-template</span></div>
      <div class="side-block">
        <div class="side-title">Arquivo</div>
        <div class="path-picker">
          <input id="configPath" aria-label="Arquivo de controle">
          <button id="pickConfigBtn" class="icon" type="button" title="Selecionar arquivo de controle">...</button>
        </div>
        <div class="button-grid">
          <button id="loadBtn">Carregar</button>
          <button id="saveBtn" class="primary">Salvar</button>
        </div>
      </div>
      <div class="side-block">
        <div class="side-title">CLI</div>
        <button id="validateBtn">Validar JSON</button>
        <button id="checkLocalBtn">Check local</button>
        <button id="checkRemoteBtn">Check remoto</button>
        <button id="planBtn" class="primary">Planejar</button>
        <label class="check"><input id="runCheck" type="checkbox" checked> Check antes de executar</label>
        <button id="executeBtn" class="danger">Executar</button>
      </div>
      <div class="side-block">
        <div class="side-title">Status</div>
        <div id="quickStatus" class="file-state">Pronto</div>
      </div>
    </aside>

    <main>
      <div class="topbar">
        <div>
          <h1>Controle de execucao</h1>
        </div>
        <div id="fileState" class="file-state"></div>
      </div>

      <nav class="tabs" aria-label="Areas">
        <button class="tab active" data-tab="editor">Editor</button>
        <button class="tab" data-tab="json">JSON</button>
        <button class="tab" data-tab="jobs">Execucoes</button>
      </nav>

      <section id="editorPanel" class="panel active">
        <div class="surface">
          <div class="section-head">
            <h2>Fluxo</h2>
            <div class="section-actions">
              <button type="button" id="flowDetailsBtn">Detalhes</button>
            </div>
          </div>
          <div id="flowBody" class="section-body"></div>
        </div>

        <div class="surface">
          <div class="section-head"><h2>Pull request</h2></div>
          <div class="section-body">
            <div class="grid">
              <label>Titulo<input data-bind="pull_request.title"></label>
              <label>Base<input data-bind="pull_request.base" placeholder="branch padrao"></label>
              <label class="wide">Body<textarea data-bind="pull_request.body"></textarea></label>
            </div>
          </div>
        </div>

        <div class="surface">
          <div class="section-head">
            <h2>Repositorios</h2>
            <button class="icon" id="addRepoBtn" title="Adicionar repositorio">+</button>
          </div>
          <div class="section-body"><div id="repositoriesList" class="list"></div></div>
        </div>

        <div class="surface">
          <div class="section-head">
            <h2>Campos Jinja</h2>
            <button class="icon" id="addValueBtn" title="Adicionar campo">+</button>
          </div>
          <div class="section-body"><div id="valuesList" class="list"></div></div>
        </div>

        <div class="surface">
          <div class="section-head">
            <h2>Vars e secrets</h2>
            <button class="icon" id="addSettingBtn" title="Adicionar item">+</button>
          </div>
          <div class="section-body"><div id="settingsList" class="list"></div></div>
        </div>

        <div class="surface">
          <div class="section-head"><h2>Excludes</h2></div>
          <div class="section-body">
            <label>Padroes ignorados<textarea id="excludeText"></textarea></label>
          </div>
        </div>
      </section>

      <section id="jsonPanel" class="panel">
        <div class="surface">
          <div class="section-head">
            <h2>JSON bruto</h2>
            <div class="checks">
              <button id="applyJsonBtn">Aplicar JSON</button>
              <button id="formatJsonBtn">Formatar</button>
            </div>
          </div>
          <div class="section-body">
            <textarea id="jsonEditor" class="json-editor" spellcheck="false"></textarea>
          </div>
        </div>
      </section>

      <section id="jobsPanel" class="panel">
        <div class="surface">
          <div class="section-head"><h2>Execucoes</h2></div>
          <div class="section-body">
            <div class="job-layout">
              <div id="jobsList" class="jobs-list"></div>
              <pre id="jobOutput">Nenhuma execucao ainda.</pre>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
  <div id="toast" class="toast"></div>

  <script>
    const initialPath = "__INITIAL_CONFIG__";
    const state = {
      data: {},
      exists: false,
      activeTab: "editor",
      selectedJob: null,
      flowDetails: false,
      expandedRepos: new Set(),
      repoSuggestions: {},
      repoSearchTimers: {},
      repoSearchTokens: {},
      repoSelectedValues: {},
      jobs: []
    };

    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => Array.from(document.querySelectorAll(selector));

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function getPath() {
      return $("#configPath").value.trim() || initialPath;
    }

    async function request(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options
      });
      const text = await response.text();
      let body = null;
      try { body = text ? JSON.parse(text) : {}; } catch (_) { body = { error: text }; }
      if (!response.ok) throw new Error(body.error || "Falha na requisicao");
      return body;
    }

    async function pickPath(kind, current, title) {
      return request("/api/pick-path", {
        method: "POST",
        body: JSON.stringify({ kind, current, title })
      });
    }

    function toast(message) {
      const el = $("#toast");
      el.textContent = message;
      el.classList.add("show");
      clearTimeout(toast.timer);
      toast.timer = setTimeout(() => el.classList.remove("show"), 2600);
    }

    async function chooseConfigPath() {
      const body = await pickPath("open-file", getPath(), "Selecionar arquivo de controle");
      if (!body.path) return;
      $("#configPath").value = body.path;
      await loadConfig();
    }

    async function chooseBoundPath(binding, kind, title) {
      const body = await pickPath(kind, getByPath(binding), title);
      if (!body.path) return;
      setByPath(binding, body.path);
      render();
      toast(kind === "folder" ? "Pasta selecionada" : "Arquivo selecionado");
    }

    async function chooseTemplateFolder() {
      const body = await pickPath("folder", templateFolderPath(), "Selecionar pasta do template padrao");
      if (!body.path) return;
      const parts = splitPath(body.path);
      state.data.template = parts.name;
      state.data.templates_root = parts.parent || state.data.templates_root;
      render();
      toast("Template padrao selecionado");
    }

    function templateFolderPath() {
      if (!state.data.templates_root || !state.data.template) return state.data.templates_root || "";
      const separator = state.data.templates_root.includes("\\") ? "\\" : "/";
      return `${state.data.templates_root}${state.data.templates_root.endsWith(separator) ? "" : separator}${state.data.template}`;
    }

    function splitPath(path) {
      const cleaned = String(path || "").replace(/[\\\/]+$/, "");
      const parts = cleaned.split(/[\\\/]+/);
      const name = parts.pop() || "";
      return { name, parent: parts.join(cleaned.includes("\\") ? "\\" : "/") };
    }

    function normalize(data) {
      const next = structuredClone(data || {});
      next.templates_root ??= "./templates";
      next.workspace ??= "./.repo-template-workspace";
      next.apply_mode ??= "api";
      next.template ??= "";
      next.branch ??= "";
      next.commit_message ??= "Apply template";
      next.pull_request ??= {};
      next.pull_request.title ??= next.pr_title || "Apply template";
      next.pull_request.body ??= next.pr_body || "Template applied by repo-template.";
      next.pull_request.base ??= next.base || "";
      next.repositories = Array.isArray(next.repositories) ? next.repositories : [];
      next.values = Array.isArray(next.values) ? next.values : [];
      next.settings = Array.isArray(next.settings) ? next.settings : [];
      next.exclude = Array.isArray(next.exclude) ? next.exclude : [];
      return next;
    }

    function setByPath(path, value) {
      const parts = path.split(".");
      let target = state.data;
      while (parts.length > 1) {
        const part = parts.shift();
        target[part] ??= {};
        target = target[part];
      }
      target[parts[0]] = value;
    }

    function getByPath(path) {
      return path.split(".").reduce((value, part) => value?.[part], state.data) ?? "";
    }

    function valueToText(value) {
      if (Array.isArray(value) || (value && typeof value === "object")) {
        return JSON.stringify(value, null, 2);
      }
      return String(value ?? "");
    }

    function parseValue(text) {
      const trimmed = text.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
        return JSON.parse(trimmed);
      }
      return text;
    }

    function repoLabel(repo) {
      if (typeof repo === "string") return repo;
      if (!repo || typeof repo !== "object") return "";
      return repo.repo || repo.full_name || (repo.owner && repo.name ? `${repo.owner}/${repo.name}` : repo.url || "");
    }

    function repoLabelAt(index) {
      return repoLabel(state.data.repositories[index]) || `repositorio ${index + 1}`;
    }

    function slotCountForArray(value) {
      return Math.max(state.data.repositories.length, Array.isArray(value) ? value.length : 0, 1);
    }

    function valueLabel(name, index) {
      return name || `campo ${index + 1}`;
    }

    function renderValueControl(kind, field, index, value, positionAttr, position, isSecret) {
      const positionPart = positionAttr ? ` ${positionAttr}="${position}"` : "";
      if (isSecret) {
        return `<input type="password" ${kind === "value" ? "data-value-field" : "data-setting-field"}="${field}"${positionPart} data-index="${index}" data-secret-mask="true" value="${escapeHtml(valueToText(value))}">`;
      }
      return `<textarea ${kind === "value" ? "data-value-field" : "data-setting-field"}="${field}"${positionPart} data-index="${index}">${escapeHtml(valueToText(value))}</textarea>`;
    }

    function renderScopedValueEditor(kind, index, name, value, isSecret = false) {
      const isArray = Array.isArray(value);
      const modeAttr = kind === "value" ? "data-value-mode" : "data-setting-mode";
      const positionAttr = kind === "value" ? "data-value-position" : "data-setting-position";

      if (!isArray) {
        return `
          <div class="value-toolbar">
            <span>${escapeHtml(name)} aplicado dessa forma para todos os repositorios</span>
            <button type="button" ${modeAttr}="array" data-index="${index}">Separar por repositorio</button>
          </div>
          <label class="wide">Valor${renderValueControl(kind, "value-single", index, value, "", "", isSecret)}</label>`;
      }

      const rows = Array.from({ length: slotCountForArray(value) }, (_, repoIndex) => {
        const repoName = repoIndex < state.data.repositories.length
          ? repoLabelAt(repoIndex)
          : `sem repositorio #${repoIndex + 1}`;
        return `
          <label>${escapeHtml(name)} para o repo: ${escapeHtml(repoName)}
            ${renderValueControl(kind, "value-array", index, value[repoIndex], positionAttr, repoIndex, isSecret)}
          </label>`;
      }).join("");

      return `
        <div class="value-toolbar wide">
          <span>Valor separado por repositorio</span>
          <button type="button" ${modeAttr}="single" data-index="${index}">Usar valor unico</button>
        </div>
        ${state.data.repositories.length
          ? '<div class="field-note wide">Editavel na secao Repositorios.</div>'
          : `<div class="repo-value-list wide">${rows}</div>`}`;
    }

    function settingScopeLabel(setting) {
      if (setting.scope === "environment") {
        return `environment${setting.environment ? `: ${setting.environment}` : ""}`;
      }
      return "repository";
    }

    function renderRepoScopedSection(title, rows) {
      if (!rows.length) return "";
      return `
        <div class="repo-scoped-section">
          <div class="repo-scoped-head">${escapeHtml(title)}</div>
          <div class="repo-scoped-items">${rows.join("")}</div>
        </div>`;
    }

    function renderRepositoryScopedEditors(repoIndex) {
      const fieldRows = state.data.values
        .map((field, index) => {
          if (!Array.isArray(field.value)) return "";
          const name = valueLabel(field.name || field.label, index);
          return `
            <label class="repo-scoped-item">${escapeHtml(name)}
              ${renderValueControl("value", "value-array", index, field.value[repoIndex], "data-value-position", repoIndex, false)}
            </label>`;
        })
        .filter(Boolean);

      const settingRows = state.data.settings
        .map((setting, index) => {
          if (!Array.isArray(setting.value)) return "";
          const name = valueLabel(setting.name, index);
          const type = setting.type === "secret" ? "secret" : "variable";
          const label = `${type} ${name} (${settingScopeLabel(setting)})`;
          return `
            <label class="repo-scoped-item">${escapeHtml(label)}
              ${renderValueControl("setting", "value-array", index, setting.value[repoIndex], "data-setting-position", repoIndex, setting.type === "secret")}
            </label>`;
        })
        .filter(Boolean);

      if (!fieldRows.length && !settingRows.length) return "";
      return `
        <div class="repo-scoped">
          ${renderRepoScopedSection("Campos Jinja deste repositorio", fieldRows)}
          ${renderRepoScopedSection("Vars e secrets deste repositorio", settingRows)}
        </div>`;
    }

    function syncRaw() {
      $("#jsonEditor").value = JSON.stringify(state.data, null, 2);
    }

    function updateStateLabels() {
      $("#fileState").textContent = `${state.exists ? "Editando" : "Novo arquivo"}: ${getPath()}`;
      $("#quickStatus").textContent = state.jobs.find((job) => job.status === "running")
        ? "Comando em execucao"
        : "Pronto";
    }

    function render() {
      state.data = normalize(state.data);
      renderFlow();
      $$("[data-bind]").forEach((input) => { input.value = getByPath(input.dataset.bind); });
      $$("#applyMode button").forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === state.data.apply_mode);
      });
      renderRepositories();
      renderValues();
      renderSettings();
      $("#excludeText").value = state.data.exclude.join("\n");
      syncRaw();
      updateStateLabels();
    }

    function renderFlow() {
      const isGit = state.data.apply_mode === "git";
      const details = state.flowDetails;
      $("#flowDetailsBtn").textContent = details ? "Ocultar" : "Detalhes";
      $("#flowBody").innerHTML = `
        <div class="grid three">
          <label>Template padrao
            <div class="path-picker">
              <input data-bind="template">
              <button class="icon" type="button" data-pick-template-folder title="Selecionar pasta do template padrao">...</button>
            </div>
          </label>
          <label>Modo de envio
            <div class="segmented" id="applyMode">
              <button data-mode="api" type="button">API</button>
              <button data-mode="git" type="button">Git</button>
            </div>
          </label>
          <label class="wide">Branch<input data-bind="branch"></label>
          <label class="wide">Commit<textarea data-bind="commit_message"></textarea></label>
          ${details ? `
            <label>Templates root
              <input value="${escapeHtml(state.data.templates_root)}" readonly>
              <span class="field-note">Definido automaticamente pela pasta anterior ao template selecionado.</span>
            </label>
            ${isGit ? `
              <label>Workspace
                <div class="path-picker">
                  <input data-bind="workspace">
                  <button class="icon" type="button" data-pick-path="workspace" data-pick-kind="folder" title="Selecionar pasta de workspace">...</button>
                </div>
              </label>
            ` : ""}
          ` : ""}
        </div>`;
    }

    function renderRepositories() {
      const list = $("#repositoriesList");
      if (!state.data.repositories.length) {
        list.innerHTML = '<div class="empty">Nenhum repositorio.</div>';
        return;
      }
      list.innerHTML = state.data.repositories.map((repo, index) => {
        const objectRepo = typeof repo === "object" && repo !== null ? repo : {};
        const expanded = state.expandedRepos.has(index);
        return `
          <div class="list-row" data-index="${index}">
            <div class="row-head">
              <span>Repositorio ${index + 1}</span>
              <div class="checks">
                <button type="button" data-toggle-repo-details="${index}">${expanded ? "Ocultar" : "Detalhes"}</button>
                <button class="icon" data-remove-repo="${index}" title="Remover">x</button>
              </div>
            </div>
            <div class="grid">
              <div class="repo-field ${expanded ? "" : "wide"}">
                <label>Owner/name ou URL</label>
                <div class="suggest-wrap">
                  <div class="path-picker repo-picker">
                    <input data-repo-field="repo" data-index="${index}" autocomplete="off" value="${escapeHtml(repoLabel(repo))}" oninput="handleRepoInput(this)" onkeyup="handleRepoInput(this)" onchange="handleRepoInput(this)" onfocus="handleRepoInput(this)">
                    <button type="button" data-repo-search-button="${index}" onclick="searchRepoNow(${index})" title="Buscar repositorio">Buscar</button>
                  </div>
                  <div class="suggestions hidden" data-repo-suggestions="${index}"></div>
                </div>
              </div>
              ${expanded ? `
                <label>Template<input data-repo-field="template" data-index="${index}" value="${escapeHtml(objectRepo.template || "")}"></label>
                <label>Branch<input data-repo-field="branch" data-index="${index}" value="${escapeHtml(objectRepo.branch || objectRepo.branch_name || "")}"></label>
                <label>Base<input data-repo-field="base" data-index="${index}" value="${escapeHtml(objectRepo.base || objectRepo.default_branch || "")}"></label>
              ` : ""}
            </div>
            ${renderRepositoryScopedEditors(index)}
          </div>`;
      }).join("");
    }

    function renderValues() {
      const list = $("#valuesList");
      if (!state.data.values.length) {
        list.innerHTML = '<div class="empty">Nenhum campo.</div>';
        return;
      }
      list.innerHTML = state.data.values.map((field, index) => {
        const name = valueLabel(field.name || field.label, index);
        return `
          <div class="list-row" data-index="${index}">
            <div class="row-head"><span>Campo ${index + 1}</span><button class="icon" data-remove-value="${index}" title="Remover">x</button></div>
            <div class="grid">
              <label>Nome<input data-value-field="name" data-index="${index}" value="${escapeHtml(field.name || "")}"></label>
              <label>Label<input data-value-field="label" data-index="${index}" value="${escapeHtml(field.label || "")}"></label>
              ${renderScopedValueEditor("value", index, name, field.value)}
            </div>
            <div class="checks">
              <label class="check"><input type="checkbox" data-value-field="required" data-index="${index}" ${field.required === false ? "" : "checked"}> Obrigatorio</label>
              <label class="check"><input type="checkbox" data-value-field="render" data-index="${index}" ${field.render === false ? "" : "checked"}> Renderizar Jinja</label>
            </div>
          </div>`;
      }).join("");
    }

    function renderSettings() {
      const list = $("#settingsList");
      if (!state.data.settings.length) {
        list.innerHTML = '<div class="empty">Nenhuma variavel ou secret.</div>';
        return;
      }
      list.innerHTML = state.data.settings.map((setting, index) => {
        const name = valueLabel(setting.name, index);
        const isEnvironment = setting.scope === "environment";
        const isSecret = setting.type === "secret";
        return `
          <div class="list-row" data-index="${index}">
            <div class="row-head"><span>Item ${index + 1}</span><button class="icon" data-remove-setting="${index}" title="Remover">x</button></div>
            <div class="grid three">
              <label>Escopo
                <select data-setting-field="scope" data-index="${index}">
                  <option value="repository" ${setting.scope !== "environment" ? "selected" : ""}>Repository</option>
                  <option value="environment" ${setting.scope === "environment" ? "selected" : ""}>Environment</option>
                </select>
              </label>
              <label>Tipo
                <select data-setting-field="type" data-index="${index}">
                  <option value="variable" ${setting.type !== "secret" ? "selected" : ""}>Variable</option>
                  <option value="secret" ${setting.type === "secret" ? "selected" : ""}>Secret</option>
                </select>
              </label>
              ${isEnvironment ? `<label>Environment<input data-setting-field="environment" data-index="${index}" value="${escapeHtml(setting.environment || "")}"></label>` : ""}
              <label>Nome<input data-setting-field="name" data-index="${index}" value="${escapeHtml(setting.name || "")}"></label>
              ${renderScopedValueEditor("setting", index, name, setting.value, isSecret)}
            </div>
          </div>`;
      }).join("");
    }

    function bindEditor() {
      document.body.addEventListener("input", (event) => {
        const target = event.target;
        if (target.matches("[data-bind]")) {
          setByPath(target.dataset.bind, target.value);
          syncRaw();
          updateStateLabels();
        }
        if (target.id === "excludeText") {
          state.data.exclude = target.value.split("\n").map((line) => line.trim()).filter(Boolean);
          syncRaw();
        }
        if (target.matches("[data-repo-field]")) {
          updateRepo(Number(target.dataset.index), target.dataset.repoField, target.value);
          if (target.dataset.repoField === "repo") {
            queueRepoSearch(Number(target.dataset.index), target.value);
          }
          syncRaw();
        }
        if (target.matches("[data-value-field]")) {
          updateValue(Number(target.dataset.index), target.dataset.valueField, target);
          syncRaw();
        }
        if (target.matches("[data-setting-field]")) {
          updateSetting(Number(target.dataset.index), target.dataset.settingField, target);
          syncRaw();
        }
      });

      document.body.addEventListener("change", (event) => {
        const target = event.target;
        if (!target.matches("select[data-setting-field]")) return;
        updateSetting(Number(target.dataset.index), target.dataset.settingField, target);
        syncRaw();
        render();
      });

      document.body.addEventListener("focusin", (event) => {
        const target = event.target;
        if (target.matches("input[data-secret-mask]")) {
          target.type = "text";
        }
        if (target.matches('input[data-repo-field="repo"]')) {
          hideAllRepoSuggestions(Number(target.dataset.index));
          queueRepoSearch(Number(target.dataset.index), target.value);
        }
      });

      document.body.addEventListener("focusout", (event) => {
        const target = event.target;
        if (target.matches("input[data-secret-mask]")) {
          target.type = "password";
        }
      });

      document.body.addEventListener("keyup", (event) => {
        const target = event.target;
        if (!target.matches('input[data-repo-field="repo"]')) return;
        updateRepo(Number(target.dataset.index), "repo", target.value);
        queueRepoSearch(Number(target.dataset.index), target.value);
        syncRaw();
      });

      document.body.addEventListener("click", (event) => {
        const target = event.target;
        const repoChoice = target.closest("[data-repo-choice]");
        const repoWrap = target.closest(".suggest-wrap");
        if (!repoWrap && !repoChoice && !target.matches("[data-repo-search-button]")) {
          hideAllRepoSuggestions();
        }
        if (target.matches("[data-pick-path]")) {
          chooseBoundPath(
            target.dataset.pickPath,
            target.dataset.pickKind || "folder",
            target.title || "Selecionar caminho"
          ).catch((error) => toast(error.message));
          return;
        }
        if (target.matches("[data-pick-template-folder]")) {
          chooseTemplateFolder().catch((error) => toast(error.message));
          return;
        }
        if (repoChoice) {
          selectRepoSuggestion(Number(repoChoice.dataset.index), repoChoice.dataset.repoChoice);
          return;
        }
        if (target.matches("[data-repo-search-button]")) {
          searchRepoNow(Number(target.dataset.repoSearchButton));
          return;
        }
        if (target.id === "flowDetailsBtn") {
          state.flowDetails = !state.flowDetails;
          render();
          return;
        }
        if (target.matches("[data-mode]")) {
          state.data.apply_mode = target.dataset.mode;
          render();
        }
        if (target.matches("[data-remove-repo]")) {
          removeRepository(Number(target.dataset.removeRepo));
          render();
        }
        if (target.matches("[data-toggle-repo-details]")) {
          toggleRepoDetails(Number(target.dataset.toggleRepoDetails));
          render();
        }
        if (target.matches("[data-remove-value]")) {
          state.data.values.splice(Number(target.dataset.removeValue), 1);
          render();
        }
        if (target.matches("[data-value-mode]")) {
          convertValueMode(Number(target.dataset.index), target.dataset.valueMode);
          render();
        }
        if (target.matches("[data-setting-mode]")) {
          convertSettingMode(Number(target.dataset.index), target.dataset.settingMode);
          render();
        }
        if (target.matches("[data-remove-setting]")) {
          state.data.settings.splice(Number(target.dataset.removeSetting), 1);
          render();
        }
      });
    }

    function addRepository() {
      state.data.repositories.push("");
      forEachRepoArray((values) => values.push(""));
    }

    function removeRepository(index) {
      state.data.repositories.splice(index, 1);
      forEachRepoArray((values) => {
        if (index < values.length) values.splice(index, 1);
      });
      const nextExpanded = new Set();
      for (const repoIndex of state.expandedRepos) {
        if (repoIndex < index) nextExpanded.add(repoIndex);
        if (repoIndex > index) nextExpanded.add(repoIndex - 1);
      }
      state.expandedRepos = nextExpanded;
      reindexRepoState(state.repoSuggestions, index);
      reindexRepoState(state.repoSearchTimers, index);
      reindexRepoState(state.repoSearchTokens, index);
      reindexRepoState(state.repoSelectedValues, index);
    }

    function reindexRepoState(values, removedIndex) {
      const next = {};
      for (const [key, value] of Object.entries(values)) {
        const index = Number(key);
        if (index < removedIndex) next[index] = value;
        if (index > removedIndex) next[index - 1] = value;
      }
      Object.keys(values).forEach((key) => delete values[key]);
      Object.assign(values, next);
    }

    function forEachRepoArray(callback) {
      for (const field of state.data.values) {
        if (Array.isArray(field.value)) callback(field.value);
      }
      for (const setting of state.data.settings) {
        if (Array.isArray(setting.value)) callback(setting.value);
      }
    }

    function toggleRepoDetails(index) {
      if (state.expandedRepos.has(index)) {
        state.expandedRepos.delete(index);
      } else {
        state.expandedRepos.add(index);
      }
    }

    function handleRepoInput(target) {
      const index = Number(target.dataset.index);
      if (state.repoSelectedValues[index] !== target.value) {
        delete state.repoSelectedValues[index];
      }
      updateRepo(index, "repo", target.value);
      queueRepoSearch(index, target.value);
      syncRaw();
    }

    function searchRepoNow(index) {
      const input = document.querySelector(`input[data-repo-field="repo"][data-index="${index}"]`);
      if (!input) return;
      delete state.repoSelectedValues[index];
      updateRepo(index, "repo", input.value);
      syncRaw();
      clearTimeout(state.repoSearchTimers[index]);
      const query = String(input.value || "").trim();
      if (query.length < 2 || query.startsWith("http://") || query.startsWith("https://") || query.startsWith("git@")) {
        state.repoSuggestions[index] = [];
        renderRepoSuggestions(index);
        return;
      }
      const token = `${Date.now()}-${Math.random()}`;
      state.repoSearchTokens[index] = token;
      runRepoSearch(index, query, token);
    }

    function queueRepoSearch(index, value) {
      const query = String(value || "").trim();
      clearTimeout(state.repoSearchTimers[index]);
      if (state.repoSelectedValues[index] === query) {
        hideRepoSuggestions(index);
        return;
      }
      if (query.length < 2 || query.startsWith("http://") || query.startsWith("https://") || query.startsWith("git@")) {
        hideRepoSuggestions(index);
        return;
      }
      const token = `${Date.now()}-${Math.random()}`;
      state.repoSearchTokens[index] = token;
      state.repoSearchTimers[index] = setTimeout(() => runRepoSearch(index, query, token), 280);
    }

    async function runRepoSearch(index, query, token) {
      try {
        const body = await request(`/api/repositories?q=${encodeURIComponent(query)}&limit=8`);
        if (state.repoSearchTokens[index] !== token) return;
        state.repoSuggestions[index] = body.error
          ? [{ full_name: "", description: body.error, disabled: true }]
          : (body.repositories || []);
        renderRepoSuggestions(index);
      } catch (error) {
        if (state.repoSearchTokens[index] !== token) return;
        state.repoSuggestions[index] = [{ full_name: "", description: error.message, disabled: true }];
        renderRepoSuggestions(index);
      }
    }

    function renderRepoSuggestions(index) {
      const target = document.querySelector(`[data-repo-suggestions="${index}"]`);
      if (!target) return;
      const suggestions = state.repoSuggestions[index] || [];
      target.classList.toggle("hidden", suggestions.length === 0);
      target.innerHTML = suggestions.map((repo) => {
        if (repo.disabled) {
          return `<div class="suggestion"><span>${escapeHtml(repo.description || "")}</span></div>`;
        }
        return `
          <button type="button" class="suggestion" data-index="${index}" data-repo-choice="${escapeHtml(repo.full_name)}">
            <strong>${escapeHtml(repo.full_name)}</strong>
            <span>${escapeHtml(repo.description || repo.visibility || "")}</span>
          </button>`;
      }).join("");
    }

    function hideRepoSuggestions(index) {
      clearTimeout(state.repoSearchTimers[index]);
      state.repoSearchTokens[index] = "";
      state.repoSuggestions[index] = [];
      renderRepoSuggestions(index);
    }

    function hideAllRepoSuggestions(exceptIndex = null) {
      const indexes = new Set([
        ...Object.keys(state.repoSuggestions).map(Number),
        ...$$("[data-repo-suggestions]").map((node) => Number(node.dataset.repoSuggestions)),
      ]);
      for (const index of indexes) {
        if (index === exceptIndex) continue;
        hideRepoSuggestions(index);
      }
    }

    function selectRepoSuggestion(index, fullName) {
      updateRepo(index, "repo", fullName);
      state.repoSelectedValues[index] = fullName;
      hideRepoSuggestions(index);
      renderRepositories();
      syncRaw();
    }

    function updateRepo(index, field, value) {
      const current = state.data.repositories[index];
      if (typeof current === "string" && field === "repo") {
        state.data.repositories[index] = value;
        return;
      }
      const next = typeof current === "object" && current !== null ? { ...current } : { repo: repoLabel(current) };
      if (field === "repo") {
        delete next.owner;
        delete next.name;
        delete next.full_name;
        delete next.url;
        if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("git@")) {
          next.url = value;
        } else {
          next.repo = value;
        }
        state.data.repositories[index] = next;
        return;
      }
      next[field] = value;
      state.data.repositories[index] = next;
    }

    function updateValue(index, field, target) {
      const item = { ...(state.data.values[index] || {}) };
      if (target.type === "checkbox") {
        item[field] = target.checked;
      } else if (field === "value-single") {
        try { item.value = parseValue(target.value); } catch (_) { item.value = target.value; }
      } else if (field === "value-array") {
        const position = Number(target.dataset.valuePosition);
        const values = Array.isArray(item.value) ? [...item.value] : [];
        try { values[position] = parseValue(target.value); } catch (_) { values[position] = target.value; }
        item.value = values;
      } else {
        item[field] = target.value;
      }
      state.data.values[index] = item;
    }

    function convertValueMode(index, mode) {
      const item = { ...(state.data.values[index] || {}) };
      if (mode === "array") {
        const current = item.value ?? "";
        item.value = Array.from({ length: Math.max(state.data.repositories.length, 1) }, () => current);
      } else {
        item.value = Array.isArray(item.value) ? (item.value[0] ?? "") : (item.value ?? "");
      }
      state.data.values[index] = item;
    }

    function updateSetting(index, field, target) {
      const item = { ...(state.data.settings[index] || {}) };
      if (field === "value-single") {
        try { item.value = parseValue(target.value); } catch (_) { item.value = target.value; }
      } else if (field === "value-array") {
        const position = Number(target.dataset.settingPosition);
        const values = Array.isArray(item.value) ? [...item.value] : [];
        try { values[position] = parseValue(target.value); } catch (_) { values[position] = target.value; }
        item.value = values;
      } else {
        item[field] = target.value;
        if (field === "scope" && target.value !== "environment") {
          delete item.environment;
        }
        if (field === "scope" && target.value === "environment") {
          item.environment ??= "";
        }
      }
      state.data.settings[index] = item;
    }

    function convertSettingMode(index, mode) {
      const item = { ...(state.data.settings[index] || {}) };
      if (mode === "array") {
        const current = item.value ?? "";
        item.value = Array.from({ length: Math.max(state.data.repositories.length, 1) }, () => current);
      } else {
        item.value = Array.isArray(item.value) ? (item.value[0] ?? "") : (item.value ?? "");
      }
      state.data.settings[index] = item;
    }

    async function loadConfig() {
      const path = encodeURIComponent(getPath());
      const body = await request(`/api/config?path=${path}`);
      state.data = normalize(body.data);
      state.exists = body.exists;
      $("#configPath").value = body.path;
      render();
      toast(body.exists ? "Arquivo carregado" : "Exemplo inicial carregado");
    }

    async function saveConfig() {
      const body = await request("/api/config", {
        method: "POST",
        body: JSON.stringify({ path: getPath(), data: state.data })
      });
      state.exists = true;
      $("#configPath").value = body.path;
      updateStateLabels();
      toast("JSON salvo");
    }

    async function startJob(action) {
      if (action === "execute") {
        const ok = confirm("Executar agora usando o arquivo de controle atual?");
        if (!ok) return;
      }
      const body = await request("/api/job", {
        method: "POST",
        body: JSON.stringify({
          action,
          path: getPath(),
          data: state.data,
          options: { check: $("#runCheck").checked }
        })
      });
      state.selectedJob = body.job.id;
      switchTab("jobs");
      await refreshJobs();
      toast("Comando iniciado");
    }

    async function refreshJobs() {
      const body = await request("/api/jobs");
      state.jobs = body.jobs;
      if (!state.selectedJob && state.jobs[0]) state.selectedJob = state.jobs[0].id;
      renderJobs();
      updateStateLabels();
    }

    function renderJobs() {
      const list = $("#jobsList");
      if (!state.jobs.length) {
        list.innerHTML = '<div class="empty">Nenhuma execucao.</div>';
        $("#jobOutput").textContent = "Nenhuma execucao ainda.";
        return;
      }
      list.innerHTML = state.jobs.map((job) => `
        <button class="job-item ${job.id === state.selectedJob ? "active" : ""}" data-job-id="${job.id}">
          <span class="job-name">${escapeHtml(job.action)}</span>
          <span class="badge ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
          <span class="job-meta">${escapeHtml(job.config_path)}</span>
          <span class="job-meta">${escapeHtml(job.started_at || "")}</span>
        </button>`).join("");

      const selected = state.jobs.find((job) => job.id === state.selectedJob) || state.jobs[0];
      $("#jobOutput").textContent = selected
        ? [`$ ${selected.command.join(" ")}`, "", selected.output.join("")].join("\n")
        : "Nenhuma execucao ainda.";
    }

    function switchTab(tab) {
      state.activeTab = tab;
      $$(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
      $$(".panel").forEach((panel) => panel.classList.remove("active"));
      $(`#${tab}Panel`).classList.add("active");
    }

    function bindChrome() {
      $$(".tab").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
      $("#loadBtn").addEventListener("click", () => loadConfig().catch((error) => toast(error.message)));
      $("#saveBtn").addEventListener("click", () => saveConfig().catch((error) => toast(error.message)));
      $("#pickConfigBtn").addEventListener("click", () => chooseConfigPath().catch((error) => toast(error.message)));
      $("#validateBtn").addEventListener("click", () => startJob("validate").catch((error) => toast(error.message)));
      $("#checkLocalBtn").addEventListener("click", () => startJob("check-local").catch((error) => toast(error.message)));
      $("#checkRemoteBtn").addEventListener("click", () => startJob("check-remote").catch((error) => toast(error.message)));
      $("#planBtn").addEventListener("click", () => startJob("plan").catch((error) => toast(error.message)));
      $("#executeBtn").addEventListener("click", () => startJob("execute").catch((error) => toast(error.message)));
      $("#addRepoBtn").addEventListener("click", () => {
        addRepository();
        render();
      });
      $("#addValueBtn").addEventListener("click", () => {
        state.data.values.push({ name: "", label: "", value: "" });
        render();
      });
      $("#addSettingBtn").addEventListener("click", () => {
        state.data.settings.push({ scope: "repository", type: "variable", name: "", value: "" });
        render();
      });
      $("#applyJsonBtn").addEventListener("click", () => {
        try {
          state.data = normalize(JSON.parse($("#jsonEditor").value));
          render();
          toast("JSON aplicado");
        } catch (error) {
          toast(error.message);
        }
      });
      $("#formatJsonBtn").addEventListener("click", () => {
        try {
          state.data = normalize(JSON.parse($("#jsonEditor").value));
          syncRaw();
          toast("JSON formatado");
        } catch (error) {
          toast(error.message);
        }
      });
      $("#jobsList").addEventListener("click", (event) => {
        const button = event.target.closest("[data-job-id]");
        if (!button) return;
        state.selectedJob = button.dataset.jobId;
        renderJobs();
      });
    }

    bindEditor();
    bindChrome();
    $("#configPath").value = initialPath;
    loadConfig().catch((error) => toast(error.message));
    setInterval(() => refreshJobs().catch(() => {}), 1400);
  </script>
</body>
</html>
"""


@dataclass
class Job:
    id: str
    action: str
    config_path: str
    command: list[str]
    status: str = "queued"
    started_at: str = ""
    ended_at: str = ""
    returncode: int | None = None
    output: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def append(self, text: str) -> None:
        with self.lock:
            self.output.append(text)
            if len(self.output) > 4000:
                self.output = self.output[-4000:]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "action": self.action,
                "config_path": self.config_path,
                "command": self.command,
                "status": self.status,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "returncode": self.returncode,
                "output": list(self.output),
            }


class WebApp:
    def __init__(self, initial_config: Path, cwd: Path) -> None:
        self.initial_config = self.resolve_path(str(initial_config), cwd)
        self.cwd = cwd
        self.jobs: dict[str, Job] = {}
        self.jobs_order: list[str] = []
        self.lock = threading.Lock()

    @staticmethod
    def resolve_path(value: str, base: Path) -> Path:
        path = Path(value or "control.json").expanduser()
        if not path.is_absolute():
            path = base / path
        return path.resolve()

    def load_config(self, value: str | None) -> dict[str, Any]:
        path = self.resolve_path(value or str(self.initial_config), self.cwd)
        if not path.exists():
            return {"path": str(path), "exists": False, "data": example_config()}
        with path.open("r", encoding="utf-8-sig") as file:
            return {"path": str(path), "exists": True, "data": json.load(file)}

    def save_config(self, value: str, data: Any) -> dict[str, Any]:
        path = self.resolve_path(value, self.cwd)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
        return {"path": str(path), "exists": True}

    def pick_path(self, kind: str, current: str | None, title: str | None = None) -> dict[str, Any]:
        if kind not in {"folder", "open-file", "save-file"}:
            raise ValueError("Tipo de seletor invalido.")
        current_path = self.resolve_path(current or str(self.cwd), self.cwd)
        selected = _pick_path_dialog(kind, current_path, title or "")
        if not selected:
            return {"path": ""}
        return {"path": str(Path(selected).expanduser().resolve())}

    def search_repositories(self, query: str, limit: int = 8) -> dict[str, Any]:
        query = " ".join(str(query or "").strip().split())
        if len(query) < 2:
            return {"repositories": []}

        limit = max(1, min(int(limit or 8), 20))
        command = [
            "gh",
            "search",
            "repos",
            query,
            "--json",
            "fullName,description,visibility",
            "--limit",
            str(limit),
        ]
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError:
            return {"repositories": [], "error": "GitHub CLI nao encontrado no PATH."}
        except subprocess.TimeoutExpired:
            return {"repositories": [], "error": "Busca no GitHub CLI excedeu o tempo limite."}

        if completed.returncode != 0:
            return {"repositories": [], "error": (completed.stderr or completed.stdout).strip()}

        try:
            raw_items = json.loads(completed.stdout or "[]")
        except ValueError:
            return {"repositories": [], "error": "GitHub CLI retornou uma resposta inesperada."}

        repositories = []
        for item in raw_items if isinstance(raw_items, list) else []:
            full_name = str(item.get("fullName") or item.get("nameWithOwner") or "")
            if not full_name:
                continue
            repositories.append(
                {
                    "full_name": full_name,
                    "description": str(item.get("description") or ""),
                    "visibility": str(item.get("visibility") or ""),
                }
            )
        return {"repositories": repositories}

    def start_job(
        self,
        action: str,
        config_path: str,
        data: Any | None,
        options: dict[str, Any] | None = None,
    ) -> Job:
        path = self.resolve_path(config_path, self.cwd)
        if data is not None:
            self.save_config(str(path), data)
        command = self.command_for(action, path, options or {})
        job = Job(
            id=uuid.uuid4().hex[:12],
            action=action,
            config_path=str(path),
            command=command,
        )
        with self.lock:
            self.jobs[job.id] = job
            self.jobs_order.insert(0, job.id)
            for stale_id in self.jobs_order[30:]:
                self.jobs.pop(stale_id, None)
            del self.jobs_order[30:]
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def command_for(self, action: str, config_path: Path, options: dict[str, Any]) -> list[str]:
        base = [sys.executable, "-m", "repo_template_cli.cli"]
        path_args = ["--config", str(config_path)]
        if action == "validate":
            return [*base, "validate", *path_args]
        if action == "check-local":
            return [*base, "check", *path_args, "--local", "--non-interactive"]
        if action == "check-remote":
            return [*base, "check", *path_args, "--non-interactive"]
        if action == "plan":
            return [*base, "run", *path_args, "--dry-run", "--yes", "--non-interactive"]
        if action == "execute":
            command = [*base, "run", *path_args, "--yes", "--non-interactive"]
            if options.get("check"):
                command.append("--check")
            return command
        raise ValueError(f"Acao desconhecida: {action}")

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.lock:
            ids = list(self.jobs_order)
        return [self.jobs[job_id].snapshot() for job_id in ids if job_id in self.jobs]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        return job.snapshot() if job else None

    def _run_job(self, job: Job) -> None:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        source_root = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = (
            source_root
            if not env.get("PYTHONPATH")
            else f"{source_root}{os.pathsep}{env['PYTHONPATH']}"
        )
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with job.lock:
            job.status = "running"
            job.started_at = _now()
        try:
            process = subprocess.Popen(
                job.command,
                cwd=str(self.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=creationflags,
            )
            assert process.stdout is not None
            for line in process.stdout:
                job.append(line)
            returncode = process.wait()
        except Exception as exc:
            job.append(f"\nErro ao iniciar comando: {exc}\n")
            returncode = 1
        with job.lock:
            job.returncode = returncode
            job.status = "done" if returncode == 0 else "failed"
            job.ended_at = _now()


class RepoTemplateServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app: WebApp) -> None:
        super().__init__(server_address, Handler)
        self.app = app


class Handler(BaseHTTPRequestHandler):
    server: RepoTemplateServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = HTML.replace("__INITIAL_CONFIG__", _json_script_string(str(self.server.app.initial_config)))
            self._send_html(html)
            return
        if parsed.path == "/api/config":
            query = parse_qs(parsed.query)
            payload = self.server.app.load_config((query.get("path") or [""])[0])
            self._send_json(payload)
            return
        if parsed.path == "/api/jobs":
            self._send_json({"jobs": self.server.app.list_jobs()})
            return
        if parsed.path == "/api/repositories":
            query = parse_qs(parsed.query)
            try:
                limit = int((query.get("limit") or ["8"])[0])
            except ValueError:
                limit = 8
            payload = self.server.app.search_repositories((query.get("q") or [""])[0], limit=limit)
            self._send_json(payload)
            return
        if parsed.path.startswith("/api/job/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = self.server.app.get_job(job_id)
            if not job:
                self._send_json({"error": "Execucao nao encontrada."}, status=404)
                return
            self._send_json({"job": job})
            return
        self._send_json({"error": "Rota nao encontrada."}, status=404)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            parsed = urlparse(self.path)
            if parsed.path == "/api/config":
                result = self.server.app.save_config(str(payload.get("path") or ""), payload.get("data"))
                self._send_json(result)
                return
            if parsed.path == "/api/pick-path":
                result = self.server.app.pick_path(
                    kind=str(payload.get("kind") or "folder"),
                    current=str(payload.get("current") or ""),
                    title=str(payload.get("title") or ""),
                )
                self._send_json(result)
                return
            if parsed.path == "/api/job":
                job = self.server.app.start_job(
                    action=str(payload.get("action") or ""),
                    config_path=str(payload.get("path") or ""),
                    data=payload.get("data"),
                    options=payload.get("options") if isinstance(payload.get("options"), dict) else {},
                )
                self._send_json({"job": job.snapshot()}, status=202)
                return
            self._send_json({"error": "Rota nao encontrada."}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Payload JSON precisa ser um objeto.")
        return data

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, body: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def serve(
    config_path: str = "control.json",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> int:
    app = WebApp(Path(config_path), Path.cwd())
    server = _create_server(host, port, app)
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"Interface web: {url}")
    print("Pressione Ctrl+C para encerrar.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _create_server(host: str, port: int, app: WebApp) -> RepoTemplateServer:
    candidates = [0] if port == 0 else [port, *range(port + 1, port + 20)]
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            return RepoTemplateServer((host, candidate), app)
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"Nao foi possivel abrir porta local: {last_error}")


def _pick_path_dialog(kind: str, current_path: Path, title: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Nao foi possivel carregar o seletor nativo: {exc}") from exc

    initialdir = _dialog_initial_dir(current_path, kind)
    initialfile = current_path.name if kind != "folder" else ""
    root = tk.Tk()
    root.withdraw()
    try:
        try:
            root.attributes("-topmost", True)
            root.update()
        except Exception:
            pass

        if kind == "folder":
            return str(
                filedialog.askdirectory(
                    parent=root,
                    title=title or "Selecionar pasta",
                    initialdir=str(initialdir),
                )
            )
        if kind == "open-file":
            return str(
                filedialog.askopenfilename(
                    parent=root,
                    title=title or "Selecionar arquivo",
                    initialdir=str(initialdir),
                    initialfile=initialfile,
                    filetypes=(("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")),
                )
            )
        return str(
            filedialog.asksaveasfilename(
                parent=root,
                title=title or "Salvar arquivo",
                initialdir=str(initialdir),
                initialfile=initialfile or "control.json",
                defaultextension=".json",
                filetypes=(("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")),
            )
        )
    finally:
        root.destroy()


def _dialog_initial_dir(current_path: Path, kind: str) -> Path:
    candidate = current_path if kind == "folder" else current_path.parent
    if candidate.is_file():
        candidate = candidate.parent
    for path in (candidate, *candidate.parents):
        if path.is_dir():
            return path
    return Path.cwd()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _json_script_string(value: str) -> str:
    return json.dumps(value)[1:-1]
