"use strict";

const byId = (id) => document.getElementById(id);
const filters = [...document.querySelectorAll("[data-filter]")];
const t = typeof ForgeLocale === "undefined" ? null : ForgeLocale.t;
let state;
let index = 0;
let view = "card";
let filter = "all";
let returnToList;
let sequenceIndex = null;
let edited = false;
let baseline = "";
let busy = false;
let conflict = false;
let approvalHint = false;
let warningMessage;
let revisionRequest;
let displayedHash = "";
let displayedEntry = null;
let followingHistory = false;
let restoringHistory = false;
let copyTimer;
let copyAttempt = 0;
let copyResult;
let copyRevisionChecked = false;

function currentCard() {
  return state.cards[index];
}

function cardStatus(id) {
  if (state.statuses?.[id]) return state.statuses[id];
  const feedback = state.feedback[id];
  return feedback ? (feedback.ok ? "accepted" : "change_requested") : "open";
}

function statusCounts() {
  const counts = {all: state.cards.length, accepted: 0, change_requested: 0, open: 0};
  for (const card of state.cards) counts[cardStatus(card.id)]++;
  return counts;
}

function currentComment() {
  return byId("comment").value;
}

function isDirty() {
  if (!state || view !== "card" || state.submission || !edited) return false;
  const saved = state.feedback[currentCard().id];
  // Editing a legacy comment can change its verdict even when the text ends up identical.
  const wouldAccept = currentComment().trim() === "";
  return currentComment() !== baseline || (Boolean(saved) && saved.ok !== wouldAccept);
}

function setStatus(element, status) {
  element.dataset.status = status;
  element.textContent = t(status);
}

function updateControls() {
  const single = Boolean(returnToList);
  const last = index === state.cards.length - 1;
  const finish = !state.submission && (single || last);
  byId("prev").disabled = busy || index === 0;
  byId("overview-link").disabled = busy;
  byId("overview-link").textContent = t(finish ? "saveOverview" : (state.submission ? "toOverview" : "overview"));
  byId("overview-link").className = finish || last ? "primary" : "secondary";
  byId("comment").readOnly = busy || Boolean(state.submission);
  byId("comment-editor").hidden = Boolean(state.submission);
  byId("editing-shortcuts").hidden = Boolean(state.submission);
  byId("next").disabled = busy;
  byId("next").hidden = last;
  byId("next").textContent = t(state.submission ? "next" : "saveNext");
  byId("next").className = finish ? "secondary" : "primary";
  byId("sequence-start").disabled = busy;
  byId("discard").hidden = !conflict || !isDirty();
  byId("discard").disabled = busy;
  byId("submit").disabled = busy;
  const hint = approvalHint ? t("clearComment") : (isDirty() ? t(conflict ? "conflict" : "unsaved") : "");
  if (byId("save-status").textContent !== hint) byId("save-status").textContent = hint;
}

function shortRevision(revision) {
  return revision.slice(0, 10);
}

function renderRevision() {
  const badge = byId("revision");
  badge.textContent = t("revision", {revision: shortRevision(state.revision)});
  badge.title = state.revision;
  const warnings = [];
  if (!state.current_revision) {
    warnings.push(t("revisionUnreadable"));
  } else if (state.current_revision !== state.revision) {
    warnings.push(t("revisionChanged", {reviewed: shortRevision(state.revision), current: shortRevision(state.current_revision)}));
  }
  const previous = state.previous_submission;
  const hasPrevious = previous && previous.revision !== state.revision;
  if (hasPrevious) {
    warnings.push(t("previousRevision", {revision: shortRevision(previous.revision)}));
  }
  byId("previous-file").hidden = !hasPrevious;
  byId("previous-path").textContent = hasPrevious ? previous.path : "";
  byId("revision-message").textContent = warnings.join("\n");
  byId("revision-notice").hidden = !warnings.length;
}

function variantLabel(variant) {
  if (/^c\d+$/.test(variant)) return t("cloze", {variant});
  if (variant.startsWith("region-")) return t("region", {number: variant.slice(7)});
  return ["forward", "reverse", "typein"].includes(variant) ? t(variant) : variant;
}

const previewSides = ["front", "back"];
const previewThemeButtons = byId("preview-theme").querySelectorAll("[data-theme]");
const themeStorageKey = "card-forge.preview-theme";
let preferredPreviewTheme = "dark";
let previewPair;
let displayedPreview;
let zoomSide;
try {
  if (sessionStorage.getItem(themeStorageKey) === "light") preferredPreviewTheme = "light";
} catch { /* The switch also works when browser storage is disabled. */ }

function previewAlt(side, label, number) {
  return side === "front" ? t("frontAlt", {label}) : t("backAlt", {number});
}

async function showPreviews(card, retry = false) {
  const hasBothThemes = Boolean(card.front_light && card.back_light);
  const originalTheme = card.front.endsWith("-dark.png") ? "dark" : "light";
  const theme = hasBothThemes ? preferredPreviewTheme : originalTheme;
  const key = [state.revision, card.id, theme].join("/");
  if (!retry && previewPair?.key === key) return;
  for (const image of previewPair?.pending || []) image.removeAttribute("src");

  byId("preview-theme").hidden = !hasBothThemes;
  for (const button of previewThemeButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.theme === theme));
  }
  const panel = byId("previews");
  panel.dataset.theme = theme;
  panel.setAttribute("aria-busy", "true");
  byId("preview-retry").hidden = true;
  byId("preview-status").hidden = false;
  byId("preview-message").textContent = t("previewLoading");
  const suffix = hasBothThemes && theme === "light" ? "_light" : "";
  const images = previewSides.map((side) => {
    byId("zoom-" + side).disabled = true;
    const image = new Image();
    image.id = side;
    image.alt = previewAlt(side, card.label, index + 1);
    image.src = card[side + suffix];
    return image;
  });
  const pair = {key, pending: images, label: card.label, number: index + 1};
  previewPair = pair;
  try {
    await Promise.all(images.map((image) => image.decode()));
    if (previewPair !== pair) return;
    // Move the decoded nodes into place together, without another network request.
    for (const image of images) {
      byId(image.id).replaceWith(image);
      byId("zoom-" + image.id).disabled = false;
    }
    displayedPreview = pair;
    byId("preview-status").hidden = true;
  } catch {
    if (previewPair !== pair) return;
    for (const image of images) image.removeAttribute("src");
    byId("preview-message").textContent = t("previewFailed");
    byId("preview-retry").hidden = false;
  } finally {
    pair.pending = [];
    if (previewPair === pair) panel.setAttribute("aria-busy", "false");
  }
}

function renderCardLabels() {
  const card = currentCard();
  byId("card-heading").textContent = t("cardHeading", {number: index + 1, total: state.cards.length});
  byId("variant").textContent = t("noteVariant", {note: card.note, variant: variantLabel(card.variant)});
  setStatus(byId("card-status"), cardStatus(card.id));
}

function renderCard() {
  const card = currentCard();
  renderCardLabels();
  showPreviews(card);
  byId("comment").value = state.feedback[card.id]?.comment || "";
  byId("saved-feedback").hidden = !state.submission || !currentComment().trim();
  byId("saved-comment").textContent = state.submission ? currentComment() : "";
  baseline = currentComment();
  edited = false;
  approvalHint = false;
}

function rowText(className, value) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = value;
  return span;
}

function renderRowLabels(button, card, i) {
  button.querySelector(".row-meta").textContent = t("rowMeta", {number: i + 1, note: card.note, variant: variantLabel(card.variant)});
  button.querySelector(".row-label").textContent = card.context || card.label || t("cardLabel", {number: i + 1});
  setStatus(button.querySelector(".status"), cardStatus(card.id));
}

function renderOverview(counts) {
  for (const button of filters) {
    const name = button.dataset.filter;
    button.setAttribute("aria-pressed", String(name === filter));
    button.querySelector(".filter-count").textContent = counts[name];
  }
  const rows = document.createDocumentFragment();
  state.cards.forEach((card, i) => {
    const status = cardStatus(card.id);
    if (filter !== "all" && status !== filter) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "row-button";
    button.dataset.cardId = card.id;
    button.dataset.index = i;
    const body = rowText("row-body", "");
    body.append(rowText("row-meta", ""), rowText("row-label", ""));
    const comment = state.feedback[card.id]?.comment;
    if (comment) body.append(rowText("row-comment", comment));
    button.append(body, rowText("status", ""));
    renderRowLabels(button, card, i);
    const li = document.createElement("li");
    li.append(button);
    rows.append(li);
  });
  byId("empty-list").hidden = Boolean(rows.childElementCount);
  byId("card-list").replaceChildren(rows);
  renderOverviewDetails(counts);
}

function renderOverviewDetails(counts) {
  if (!byId("empty-list").hidden) {
    const messages = {accepted: "emptyAccepted", change_requested: "emptyChanges", open: "emptyOpen", all: "emptyAll"};
    byId("empty-list").textContent = t(messages[filter]);
  }
  const submission = state.submission;
  const continueReview = !submission && counts.open > 0;
  byId("sequence-start").className = continueReview ? "primary" : "secondary";
  byId("sequence-start").textContent = sequenceIndex === null ? t("startSequence") : t("resume", {number: sequenceIndex + 1});
  byId("submit").className = continueReview ? "secondary" : "primary";
  byId("submit").hidden = Boolean(submission);
  byId("copy").hidden = !submission;
  byId("finish-heading").hidden = !submission;
  let detail = t("submissionHint");
  if (counts.open) detail = counts.open === 1 ? t("oneOpen") : t("manyOpen", {count: counts.open});
  byId("finish-detail").hidden = Boolean(submission);
  byId("finish-detail").textContent = submission ? "" : detail;
  byId("submission-file").hidden = !submission;
  byId("submission-path").textContent = submission ? submission.path : "";
  if (submission) {
    const prompt = byId("prompt");
    const text = t("handoffPrompt", {path: submission.path});
    if (prompt.value !== text) {
      const {selectionStart, selectionEnd, selectionDirection} = prompt;
      const whole = selectionStart === 0 && selectionEnd === prompt.value.length;
      prompt.value = text;
      if (!byId("manual-copy").hidden) prompt.setSelectionRange(selectionStart, whole ? text.length : selectionEnd, selectionDirection);
    }
  }
}

function renderProgress(counts) {
  const progress = byId("review-progress");
  const checked = counts.all - counts.open;
  const summary = t("progress", {checked, total: counts.all});
  const breakdown = t(counts.accepted === 1 ? "breakdownOne" : "breakdown",
    {accepted: counts.accepted, changes: counts.change_requested, open: counts.open});
  byId("progress-label").textContent = summary;
  progress.setAttribute("aria-valuemax", counts.all);
  progress.setAttribute("aria-valuenow", checked);
  progress.setAttribute("aria-valuetext", summary + ". " + breakdown);
  progress.title = breakdown;
  byId("progress-fill").setAttribute("width", 100 * checked / counts.all);
}

function render() {
  const counts = statusCounts();
  byId("review").dataset.view = view;
  renderProgress(counts);
  if (view === "card") resetCopyFeedback();
  byId("card-view").hidden = view !== "card";
  byId("overview").hidden = view !== "overview";
  renderRevision();
  if (view === "overview") renderOverview(counts);
  else renderCard();
  updateControls();
  byId("review").hidden = false;
}

function writeHash(replace = false, anchor = returnToList) {
  const params = new URLSearchParams();
  if (view === "card") params.set("karte", currentCard().id);
  if (view === "overview" || returnToList) params.set("ansicht", "uebersicht");
  if (view === "overview" || filter !== "all") params.set("filter", filter);
  if (sequenceIndex !== null) params.set("folge", state.cards[sequenceIndex].id);
  const hash = "#" + params;
  replace ||= hash === location.hash;
  const step = replace && Number.isInteger(history.state?.step) ? history.state.step : (displayedEntry?.step ?? -1) + 1;
  displayedEntry = {step, anchor};
  if (replace) history.replaceState(displayedEntry, "", hash);
  else history.pushState(displayedEntry, "", hash);
  displayedHash = hash;
}

function showCard(i) {
  index = i;
  if (!returnToList && sequenceIndex !== null) sequenceIndex = index;
  view = "card";
  conflict = false;
  warn();
  writeHash();
  render();
  focusView();
}

function showOverview() {
  const context = returnToList;
  returnToList = null;
  view = "overview";
  conflict = false;
  warn();
  writeHash(false, context);
  render();
  focusView(context);
}

function focusView(context) {
  if (view === "overview" && context) {
    const rows = [...byId("card-list").querySelectorAll("button")];
    const target = rows.find((row) => row.dataset.cardId === context.id) ||
      rows[Math.min(context.position, rows.length - 1)] || filters.find((button) => button.dataset.filter === filter);
    target.focus({preventScroll: true});
    window.scrollTo(0, context.scroll);
    target.scrollIntoView({block: "nearest"});
  } else {
    byId(view === "card" ? "card-heading" : "overview-heading").focus({preventScroll: true});
    window.scrollTo(0, 0);
  }
}

function renderWarning() {
  const notice = byId("notice");
  const message = warningMessage ? warningMessage() : "";
  notice.textContent = message;
  notice.hidden = !message;
}

function warn(messageFactory) {
  warningMessage = messageFactory;
  renderWarning();
  if (warningMessage) byId("notice").scrollIntoView({block: "nearest"});
}

function errorDetail(error) {
  if (error.localeKey && ForgeLocale.has(error.localeKey)) return t(error.localeKey);
  return error.status ? "HTTP " + error.status : "";
}

async function request(endpoint, payload) {
  const options = {cache: "no-store"};
  if (payload) {
    options.method = "POST";
    options.headers = {"Content-Type": "application/json"};
    options.body = JSON.stringify(payload);
  }
  const response = await fetch("api/" + endpoint, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error("HTTP " + response.status);
    error.localeKey = body?.error_key;
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function load() {
  byId("retry").hidden = true;
  byId("loading").hidden = false;
  warn();
  try {
    const data = await request("state");
    if (!data.cards.length) throw Object.assign(new Error(), {localeKey: "noCards"});
    state = data;
    const names = state.deck.split("::");
    byId("deck").textContent = names.pop();
    byId("parent-deck").textContent = names.join(" / ");
    byId("parent-deck").hidden = !names.length;
    document.title = t("deckTitle", {deck: state.deck});
    applyLocation(false);
  } catch (error) {
    warn(() => t("loadFailed", {error: errorDetail(error)}).trim());
    byId("retry").hidden = false;
  } finally {
    byId("loading").hidden = true;
  }
}

function applyLocation(moveFocus) {
  if (byId("zoom").open) byId("zoom").close();
  const params = new URLSearchParams(location.hash.slice(1));
  const overview = params.get("ansicht") === "uebersicht";
  const savedFilter = params.get("filter");
  filter = filters.some((button) => button.dataset.filter === savedFilter) ? savedFilter : "all";
  const wanted = state.cards.findIndex((card) => card.id === params.get("karte"));
  const resume = state.cards.findIndex((card) => card.id === params.get("folge"));
  sequenceIndex = resume < 0 ? null : resume;
  const firstOpen = state.cards.findIndex((card) => cardStatus(card.id) === "open");
  index = wanted >= 0 ? wanted : Math.max(0, firstOpen);
  view = wanted < 0 && (overview || state.submission || firstOpen < 0) ? "overview" : "card";
  // Older tabs stored the row anchor directly in history.state.
  const anchor = history.state?.anchor || (history.state?.id ? history.state : null);
  returnToList = null;
  if (view === "card") {
    if (overview) returnToList = anchor?.id === currentCard().id ? anchor : {id: currentCard().id, position: 0, scroll: 0};
    else sequenceIndex = index;
  }
  conflict = false;
  warn();
  writeHash(true, view === "overview" ? anchor : returnToList);
  render();
  if (moveFocus) focusView(anchor);
}

function restoreLocation() {
  const step = history.state?.step;
  if (Number.isInteger(step) && step !== displayedEntry.step) {
    restoringHistory = true;
    history.go(displayedEntry.step - step);
  } else {
    // A manually entered fragment has no Forge history entry yet.
    displayedEntry = {...displayedEntry, step: displayedEntry.step + 1};
    history.replaceState(displayedEntry, "", displayedHash);
  }
}

async function followLocation() {
  if (!displayedEntry) return;
  if (location.hash === displayedHash) {
    restoringHistory = false;
    return;
  }
  // A save already in flight settles the most recent URL before its own navigation.
  if (followingHistory || restoringHistory || busy) return;
  if (conflict && isDirty()) {
    restoreLocation();
    return;
  }
  followingHistory = true;
  const original = displayedHash;
  const dirty = isDirty();
  try {
    if (dirty && !await persistCard(false)) {
      if (original === displayedHash && location.hash !== displayedHash) restoreLocation();
      return;
    }
    if (location.hash !== displayedHash) applyLocation(true);
    else if (dirty) render();
  } finally {
    followingHistory = false;
  }
}

function followAfterWrite(saved) {
  if (location.hash === displayedHash) return false;
  if (saved) applyLocation(true);
  else restoreLocation();
  return true;
}

async function mutate(endpoint, payload) {
  const localText = isDirty() ? currentComment() : null;
  const cardId = currentCard().id;
  const before = state.feedback[cardId];
  busy = true;
  updateControls();
  warn();
  try {
    state = await request(endpoint, {...payload, version: state.version});
    return true;
  } catch (error) {
    if (error.status !== 409) {
      warn(() => t("actionFailed", {error: errorDetail(error)}).trim());
      return false;
    }
    try {
      state = await request("state");
      if (state.submission) {
        showOverview();
        warn(() => t("alreadySubmitted") + (localText !== null ? "\n" + t("localInput", {comment: localText}) : ""));
      } else {
        render();
        const theirs = state.feedback[cardId];
        if (localText !== null) {
          byId("comment").value = localText;
          edited = true;
        }
        conflict = view === "card" && (before?.ok !== theirs?.ok || before?.comment !== theirs?.comment);
        if (conflict) {
          const verdict = cardStatus(cardId);
          const pending = isDirty();
          warn(() => [t("cardConflict"), t("savedVerdict", {status: t(verdict)}),
            t("savedComment", {comment: theirs?.comment || t("emptyValue")}), pending ? t("conflictNext") : ""]
            .filter(Boolean).join("\n"));
        } else {
          warn(() => t("otherWindow"));
        }
      }
    } catch (reloadError) {
      warn(() => t("refreshFailed", {error: errorDetail(reloadError)}).trim());
    }
    return false;
  } finally {
    busy = false;
    updateControls();
  }
}

async function persistCard(confirm, accept = false) {
  const status = cardStatus(currentCard().id);
  if (state.submission || (!isDirty() && !(confirm && status === "open") && !(accept && status !== "accepted"))) return true;
  const text = currentComment();
  const ok = !text.trim();
  return mutate("save", {id: currentCard().id, ok, comment: ok ? "" : text});
}

async function leaveCard(action, shortcut = false) {
  if (busy || followingHistory || restoringHistory || view !== "card") return;
  const last = index === state.cards.length - 1;
  if ((action === "prev" && index === 0) || (action === "browse-next" && last)) return;
  const confirm = action === "accept" || action === "next" || (action === "overview" && !shortcut && (returnToList || last));
  if (conflict && isDirty() && (shortcut || !confirm)) {
    byId("discard").focus();
    return;
  }
  if (action === "accept" && currentComment().trim()) {
    approvalHint = true;
    updateControls();
    byId("comment").focus();
    return;
  }
  const saved = await persistCard(confirm, action === "accept");
  if (followAfterWrite(saved) || !saved) return;
  if (action === "overview" || (action === "accept" && last)) {
    if (!returnToList && last && confirm) sequenceIndex = null;
    showOverview();
  } else {
    returnToList = null;
    sequenceIndex = index;
    showCard(index + (action === "prev" ? -1 : 1));
  }
}

function zoom(side) {
  if (byId("zoom-" + side).disabled) return;
  const image = byId(side);
  if (!image.complete || !image.naturalWidth) return;
  // Use the decoded pixels already on screen. The local server sends no-store.
  const canvas = byId("zoom-image");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  canvas.getContext("2d").drawImage(image, 0, 0);
  zoomSide = side;
  renderZoomLabels();
  byId("zoom-size").setAttribute("aria-pressed", "false");
  byId("zoom").showModal();
  syncZoomSize();
  byId("zoom-scroll").scrollTo(0, 0);
}

function renderZoomLabels() {
  byId("zoom-image").setAttribute("aria-label", byId(zoomSide).alt);
  byId("zoom-title").textContent = t("zoomTitle", {side: t(zoomSide), number: index + 1});
}

function syncZoomSize() {
  if (!byId("zoom").open) return;
  const fits = byId("zoom-image").width <= byId("zoom-scroll").clientWidth;
  byId("zoom-size").hidden = fits;
  if (fits) byId("zoom-size").setAttribute("aria-pressed", "false");
}

function refreshSubmittedRevision() {
  if (!state?.submission || document.hidden) return;
  if (!revisionRequest) {
    revisionRequest = request("state").then((fresh) => {
      state.current_revision = fresh.current_revision;
      state.previous_submission = fresh.previous_submission;
    }).catch(() => {
      state.current_revision = null;
    }).finally(() => {
      renderRevision();
      revisionRequest = null;
    });
  }
  return revisionRequest;
}

function resetCopyFeedback() {
  copyAttempt++;
  clearTimeout(copyTimer);
  copyResult = null;
  copyRevisionChecked = false;
  delete byId("copy").dataset.copied;
  byId("manual-copy").hidden = true;
  renderCopyFeedback();
}

function renderCopyFeedback() {
  const copied = copyResult === "copied";
  byId("copy").textContent = t(copied ? "copied" : "copyPrompt");
  let message = copyResult ? t(copied ? "copySuccess" : "copyManual") : "";
  if (copyRevisionChecked && !state.current_revision) message += " " + t("copyUnreadable");
  else if (copyRevisionChecked && state.current_revision !== state.revision) {
    message += " " + t("copyStale", {reviewed: shortRevision(state.revision), current: shortRevision(state.current_revision)});
  }
  byId("copy-status").textContent = message;
  byId("copy-status").classList.toggle("visually-hidden", copied);
}

async function copyPrompt() {
  resetCopyFeedback();
  const attempt = copyAttempt;
  const prompt = byId("prompt");
  // Start both in the click handler so clipboard access retains user activation.
  const refresh = refreshSubmittedRevision();
  let copied = false;
  try {
    await navigator.clipboard.writeText(prompt.value);
    copied = true;
  } catch {
    if (attempt !== copyAttempt) return;
    byId("manual-copy").hidden = false;
    prompt.focus();
    prompt.select();
    try { copied = document.execCommand("copy"); }
    catch { /* The selected text remains available for manual copying. */ }
  }
  if (attempt !== copyAttempt) return;
  byId("manual-copy").hidden = copied;
  copyResult = copied ? "copied" : "manual";
  if (copied) {
    byId("copy").dataset.copied = "true";
    byId("copy").focus();
    copyTimer = setTimeout(resetCopyFeedback, 2500);
  }
  renderCopyFeedback();
  await refresh;
  if (attempt !== copyAttempt) return;
  copyRevisionChecked = true;
  renderCopyFeedback();
}

function refreshLanguage() {
  // Translate in place. Re-rendering a card resets its draft, and rebuilding
  // the list detaches the focused row even when its card ID stays unchanged.
  const {scrollX, scrollY} = window;
  renderWarning();
  if (!state) return;
  document.title = t("deckTitle", {deck: state.deck});
  const counts = statusCounts();
  renderRevision();
  renderProgress(counts);
  if (view === "overview") {
    for (const row of byId("card-list").querySelectorAll("button")) {
      const i = Number(row.dataset.index);
      renderRowLabels(row, state.cards[i], i);
    }
    renderOverviewDetails(counts);
  } else {
    renderCardLabels();
    if (displayedPreview) {
      for (const side of previewSides) byId(side).alt = previewAlt(side, displayedPreview.label, displayedPreview.number);
    }
    for (const image of previewPair?.pending || []) {
      image.alt = previewAlt(image.id, previewPair.label, previewPair.number);
    }
    if (!byId("preview-status").hidden) {
      byId("preview-message").textContent = t(byId("preview-retry").hidden ? "previewLoading" : "previewFailed");
    }
    if (byId("zoom").open) renderZoomLabels();
  }
  updateControls();
  renderCopyFeedback();
  window.scrollTo(scrollX, scrollY);
}

byId("prev").addEventListener("click", () => leaveCard("prev"));
byId("overview-link").addEventListener("click", () => leaveCard("overview"));
byId("sequence-start").addEventListener("click", () => {
  if (busy || view !== "overview") return;
  sequenceIndex = sequenceIndex ?? 0;
  showCard(sequenceIndex);
});
byId("retry").addEventListener("click", () => t ? load() : location.reload());
byId("comment").addEventListener("input", () => {
  edited = true;
  approvalHint = false;
  updateControls();
});
byId("discard").addEventListener("click", () => {
  conflict = false;
  warn();
  renderCard();
  updateControls();
  byId("comment").focus();
});
byId("feedback-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!byId("next").hidden) leaveCard("next");
});
for (const button of filters) {
  button.addEventListener("click", () => {
    if (busy) return;
    filter = button.dataset.filter;
    writeHash();
    renderOverview(statusCounts());
  });
}
byId("card-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-card-id]");
  if (busy || !button) return;
  const position = [...byId("card-list").querySelectorAll("button")].indexOf(button);
  returnToList = {id: button.dataset.cardId, position, scroll: window.scrollY};
  writeHash(true, returnToList);
  showCard(Number(button.dataset.index));
});
byId("submit").addEventListener("click", async () => {
  if (busy || view !== "overview" || state.submission) return;
  const saved = await mutate("submit", {});
  if (!followAfterWrite(saved) && saved) {
    render();
    byId("copy").focus();
  }
});
byId("copy").addEventListener("click", copyPrompt);
for (const button of previewThemeButtons) {
  button.addEventListener("click", () => {
    preferredPreviewTheme = button.dataset.theme;
    try { sessionStorage.setItem(themeStorageKey, preferredPreviewTheme); }
    catch { /* Keep the in-memory preference. */ }
    showPreviews(currentCard());
  });
}
byId("preview-retry").addEventListener("click", () => showPreviews(currentCard(), true));
byId("zoom-front").addEventListener("click", () => zoom("front"));
byId("zoom-back").addEventListener("click", () => zoom("back"));
byId("zoom-close").addEventListener("click", () => byId("zoom").close());
byId("zoom-size").addEventListener("click", (event) => {
  const toggle = event.currentTarget;
  toggle.setAttribute("aria-pressed", String(toggle.getAttribute("aria-pressed") !== "true"));
  byId("zoom-scroll").scrollTo(0, 0);
});
byId("zoom").addEventListener("close", () => {
  if (byId("zoom").open) return;
  byId("zoom-image").width = 0;
  byId("zoom-image").height = 0;
});
window.addEventListener("resize", syncZoomSize);
window.addEventListener("focus", refreshSubmittedRevision);
document.addEventListener("visibilitychange", refreshSubmittedRevision);
history.scrollRestoration = "manual";
window.addEventListener("popstate", followLocation);
window.addEventListener("hashchange", followLocation);
const letterShortcuts = byId("letter-shortcuts");
try { letterShortcuts.checked = localStorage.getItem("forge-review-letter-shortcuts") !== "off"; }
catch { /* Private browsers may disable local storage. */ }
letterShortcuts.addEventListener("change", () => {
  try { localStorage.setItem("forge-review-letter-shortcuts", letterShortcuts.checked ? "on" : "off"); }
  catch { /* The preference still applies to this page. */ }
});
document.addEventListener("keydown", (event) => {
  if (!state || view !== "card" || busy || document.querySelector("dialog[open]") ||
      event.defaultPrevented || event.isComposing || event.repeat || event.keyCode === 229 ||
      event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (event.target.closest?.("input, textarea, select, button, a, summary, [contenteditable], [role='textbox']")) return;
  const arrows = {ArrowLeft: "prev", ArrowRight: "browse-next", Escape: "overview"};
  if (Object.hasOwn(arrows, event.key)) {
    event.preventDefault();
    leaveCard(arrows[event.key], true);
  } else if (!state.submission && letterShortcuts.checked) {
    const key = event.key.toLowerCase();
    if (key === "c" || key === "ä") {
      event.preventDefault();
      byId("comment").focus();
    } else if (key === "p") {
      event.preventDefault();
      leaveCard("accept", true);
    }
  }
});
window.addEventListener("beforeunload", (event) => {
  if (isDirty() || busy) {
    event.preventDefault();
    event.returnValue = true;
  }
});
if (t) {
  ForgeLocale.start(refreshLanguage);
  load();
} else {
  byId("loading").hidden = true;
  byId("ui-language").disabled = true;
  warn(() => "Sprachpaket fehlt. Lade die Seite neu. Falls die Meldung bleibt, starte die Forge-Review neu.\n" +
    "Language files unavailable. Reload this page. If this message persists, restart the Forge review.");
  byId("retry").textContent = "Neu laden / Reload";
  byId("retry").hidden = false;
}
