import QtQuick
import Quickshell.Io

// Quickshell's tooling metadata omits QProcess::ExitStatus; runtime exit
// signals are covered by the offscreen process integration test.
// qmllint disable signal-handler-parameters

QtObject {
    id: service
    property string executable: decodeURIComponent(String(Qt.resolvedUrl("bin/zorya-rgb")).replace(/^file:\/\//, ""))
    property var state: ({on: true, color: "#FFFFFF", brightness: 100, effect: "static", speed: 1, secondary_color: "#8A6CFF", devices: [], presets: [], connected: false})
    property var devices: []
    property var diagnostics: null
    property string error: ""
    property string lastError: ""
    property string lastErrorOperation: ""
    property string lastBackendErrorAt: ""
    property var observedReadErrors: ({})
    property double lastErrorTime: 0
    property bool actionInFlight: false
    property bool updateReloadRequired: false
    property string updateMessage: ""
    property var updateInfo: null
    property bool updateChecked: false
    property bool updateChecking: false
    property string updateError: ""
    readonly property bool updateAvailable: updateInfo !== null && updateInfo.update_available === true
    readonly property bool updateInstalling: ((action.running || actionInFlight) && operation === "update") || updateReloadRequired || pluginReload.running || queue.some(function(job) { return job.kind === "update" })
    property string updateResponse: ""
    property string updateStderr: ""
    property bool reportBusy: false
    property string reportError: ""
    property string supportMessage: ""
    property var supportReport: null
    property string createdIssueUrl: ""
    property string reportResponse: ""
    property string reportStderr: ""
    property string reportOperation: ""
    property bool active: false
    property int pollFailures: 0
    readonly property bool busy: planLoading || setupRunning || action.running || actionInFlight || queue.length > 0 || Object.keys(pending).length > 0
    property string operation: ""
    property var pending: ({})
    property var queue: []
    property int revision: 0
    property int readRevision: 0
    property string readKind: "status"
    property bool refreshRequested: false
    property bool pairSucceeded: false

    // This state belongs to the service, so closing the panel never cancels setup.
    property var setupPlan: null
    property bool planLoading: false
    property bool setupRunning: false
    property bool setupSucceeded: false
    property string setupError: ""
    property string setupHint: ""
    property string setupStage: ""
    property string setupStepId: ""
    property var setupQueue: []
    property int setupCompleted: 0
    property int setupTotal: 0
    property int setupDeviceCount: 0
    property string setupResponse: ""
    property string setupStderr: ""
    property bool startAfterPlan: false
    property bool planRequested: false
    property bool deferredPlan: false
    property bool deferredPlanStart: false
    property var reviewedActions: []
    readonly property bool needsSetup: (setupPlan !== null ? setupPlan.ready !== true : !state.connected && setupError !== "") && !setupSucceeded
    onActiveChanged: {
        if (active && !planRequested) requestPlan(false)
        if (active && !updateChecked) checkUpdates(false)
    }
    onSetupErrorChanged: { if (setupError) captureError(setupError, "setup" + (setupStepId ? ": " + setupStepId : "")) }
    function captureError(message, context, timestamp) {
        var at = timestamp === undefined ? Date.now() : Number(timestamp) * 1000
        if (!message || (timestamp !== undefined && (!isFinite(at) ? lastErrorTime > 0 : at < lastErrorTime))) return
        lastErrorTime = isFinite(at) ? at : Date.now()
        lastError = String(message)
        lastErrorOperation = context || "backend"
    }
    function checkUpdates(force) {
        if (updateChecking || updateInstalling) return
        updateChecked = true
        updateChecking = true
        updateError = ""
        updateResponse = ""
        updateStderr = ""
        updateCheck.command = [executable, "updates", "check"].concat(force ? ["--force"] : [])
        updateCheck.running = true
    }
    function installUpdate() {
        if (!updateAvailable || updateInstalling || reportBusy || !updateInfo.tag) return
        command(["updates", "apply", "--tag", String(updateInfo.tag)], "update")
    }
    function prepareReport() {
        if (reportBusy || updateInstalling) return
        supportReport = null
        createdIssueUrl = ""
        supportMessage = ""
        runSupport(["support", "report", "--error=" + lastError, "--operation=" + lastErrorOperation], "report")
    }
    function copyReport() {
        if (!reportBusy && !updateInstalling && supportReport) runSupport(["support", "copy"], "copy")
    }
    function submitReport() {
        if (reportBusy || updateInstalling || createdIssueUrl || !supportReport || supportReport.submit_available !== true || !supportReport.fingerprint) return
        runSupport(["support", "submit", "--fingerprint", String(supportReport.fingerprint)], "submit")
    }
    function retrySupport() {
        if (reportOperation === "submit") submitReport()
        else if (reportOperation === "copy") copyReport()
        else prepareReport()
    }
    function runSupport(args, kind) {
        reportBusy = true
        reportError = ""
        reportResponse = ""
        reportStderr = ""
        reportOperation = kind
        support.command = [executable].concat(args)
        support.running = true
    }
    property Process updateCheck: Process {
        stdout: StdioCollector { onStreamFinished: service.updateResponse = text }
        stderr: StdioCollector { onStreamFinished: service.updateStderr = text.trim().slice(0, 500) }
        onExited: function(code) {
            Qt.callLater(function() {
                var data = null
                try { data = JSON.parse(service.updateResponse) } catch (exception) { /* Report below. */ }
                service.updateChecking = false
                if (code !== 0 || !data || data.ok !== true) {
                    service.updateError = data && data.error ? String(data.error) : service.updateStderr || "Could not check GitHub releases. Try again."
                    service.captureError(service.updateError, "updates check")
                } else service.updateInfo = data
            })
        }
    }
    property Process pluginReload: Process {
        command: ["omarchy-shell", "shell", "rescanPlugins"]
        onExited: function(code) {
            service.updateReloadRequired = false
            if (code !== 0) service.updateMessage = "Update installed. Close and reopen ZoryaRGB to load the new version."
        }
    }
    property Process support: Process {
        stdout: StdioCollector { onStreamFinished: service.reportResponse = text }
        stderr: StdioCollector { onStreamFinished: service.reportStderr = text.trim().slice(0, 500) }
        onExited: function(code) {
            Qt.callLater(function() {
                var data = null
                try { data = JSON.parse(service.reportResponse) } catch (exception) { /* Report below. */ }
                service.reportBusy = false
                if (code !== 0 || !data || data.ok !== true || (service.reportOperation === "report" && (!data.body || !data.issue_url)) || (service.reportOperation === "submit" && !data.issue_url)) {
                    service.reportError = data && data.error ? String(data.error) : service.reportStderr || (service.reportOperation === "submit" ? "Could not create the GitHub issue. Retry or open the browser form." : "Could not prepare the diagnostic report. Retry.")
                } else if (service.reportOperation === "report") service.supportReport = data
                else if (service.reportOperation === "submit") {
                    service.createdIssueUrl = String(data.issue_url)
                    service.supportMessage = (data.already_submitted === true || data.reused === true) ? "This report already has a GitHub issue." : "GitHub issue created with the full diagnostic report."
                } else service.supportMessage = "Full diagnostic report copied."
            })
        }
    }

    function requestPlan(start) {
        if (onboarding.running || setupRunning || planLoading || updateInstalling) return
        commitPending()
        if (action.running || actionInFlight || queue.length) {
            deferredPlan = true
            deferredPlanStart = start === true
            return
        }
        reviewedActions = setupPlan && Array.isArray(setupPlan.steps) ? setupPlan.steps.filter(function(step) { return step.status === "needed" && step.id !== "verify" }) : []
        startAfterPlan = start === true
        planRequested = true
        planLoading = true
        setupResponse = ""
        setupStderr = ""
        onboarding.command = [executable, "onboarding", "plan"]
        onboarding.running = true
    }
    function startSetup() { requestPlan(true) }
    function nextSetupStep() {
        if (!setupQueue.length) {
            setupRunning = false
            setupSucceeded = true
            if (setupPlan) setupPlan = merged(setupPlan, {ready: true, summary: "Connection checked. Choose devices to control their lighting."})
            setupStage = "Connection checked"
            next()
            refresh()
            return
        }
        var jobs = setupQueue.slice(), step = jobs.shift()
        setupQueue = jobs
        setupStage = step.label
        setupStepId = step.id
        setupResponse = ""
        setupStderr = ""
        onboarding.command = [executable, "onboarding", "run", "--step", step.id]
        onboarding.running = true
    }
    function finishOnboarding(code) {
        var data = null
        try { data = JSON.parse(setupResponse) } catch (exception) { /* Report below. */ }
        var wasPlan = planLoading
        planLoading = false
        if (code !== 0 || !data || data.ok !== true || (!wasPlan && data.error)) {
            setupRunning = false
            setupSucceeded = false
            setupError = data && data.error ? String(data.error) : setupStderr || "Setup returned an invalid response (exit " + code + ")."
            setupHint = data && data.hint ? String(data.hint) : "Review the details, then retry to check which steps are still needed."
            startAfterPlan = false
            return
        }
        if (data.diagnostics) diagnostics = data.diagnostics
        if (Array.isArray(data.devices)) {
            devices = data.devices
            setupDeviceCount = data.devices.length
        }
        if (wasPlan) {
            setupPlan = data
            if (data.ready !== true) setupSucceeded = false
            if (data.error) {
                setupError = String(data.error)
                setupHint = data.hint ? String(data.hint) : "Resolve the blocked steps, then check again."
                startAfterPlan = false
                return
            }
            if (!startAfterPlan) return
            startAfterPlan = false
            var steps = Array.isArray(data.steps) ? data.steps : []
            var blocked = steps.filter(function(step) { return step.required && step.status === "blocked" })
            if (blocked.length) {
                setupError = blocked.map(function(step) { return step.label + ": " + step.description }).join("\n")
                setupHint = "Resolve the blocked steps, then retry."
                return
            }
            var changed = steps.some(function(step) {
                if (step.status !== "needed" || step.id === "verify") return false
                return !reviewedActions.some(function(reviewed) {
                    return reviewed.id === step.id && reviewed.description === step.description && reviewed.required === step.required
                })
            })
            if (changed) {
                setupError = "The setup plan changed. Review the updated steps before starting."
                setupHint = "Click Start setup again after reviewing the actions above."
                return
            }
            setupError = ""
            setupHint = ""
            setupSucceeded = false
            // Always verify independently after the currently needed steps.
            setupQueue = steps.filter(function(step) { return step.status === "needed" && step.id !== "verify" })
            setupQueue.push({id: "verify", label: "Checking connection and devices"})
            setupCompleted = 0
            setupTotal = setupQueue.length
            setupRunning = true
        } else {
            setupCompleted++
            if (setupPlan && Array.isArray(setupPlan.steps)) {
                setupPlan = merged(setupPlan, {steps: setupPlan.steps.map(function(step) {
                    return step.id === setupStepId ? merged(step, {status: "ready"}) : step
                })})
            }
        }
        Qt.callLater(nextSetupStep)
    }
    property Process onboarding: Process {
        stdout: StdioCollector { onStreamFinished: service.setupResponse = text }
        stderr: StdioCollector { onStreamFinished: service.setupStderr = text.trim().slice(0, 1500) }
        onExited: function(code) { Qt.callLater(function() { service.finishOnboarding(code); if (!service.setupRunning) service.next() }) }
    }

    function merged(base, patch) {
        var result = ({})
        for (var key in base) result[key] = base[key]
        for (var field in patch) result[field] = patch[field]
        return result
    }
    function update(patch) {
        if (updateInstalling) return
        revision++
        state = merged(state, patch)
        pending = merged(pending, patch)
        // Throttle the stream: restarting on every move would wait for a pause.
        if (!debounce.running) debounce.start()
    }
    function commitPending() {
        debounce.stop()
        if (!Object.keys(pending).length) return
        var patch = pending
        pending = ({})
        enqueue(["set", "--json", JSON.stringify(patch)], "set")
    }
    function enqueue(args, kind) {
        pollFailures = 0
        var jobs = queue.slice()
        // Coalesce consecutive pending writes, preserving preset/setup order.
        if (kind === "set" && jobs.length && jobs[jobs.length - 1].kind === "set") {
            var previous = jobs[jobs.length - 1]
            previous.args = ["set", "--json", JSON.stringify(merged(JSON.parse(previous.args[2]), JSON.parse(args[2])))]
        } else jobs.push({args: args, kind: kind})
        queue = jobs
        next()
    }
    function command(args, kind) {
        if (updateInstalling) return
        commitPending()
        enqueue(args, kind || args[0])
    }
    function next() {
        if (action.running || actionInFlight || setupRunning || planLoading) return
        if (queue.length && queue[0].kind === "update" && read.running) return
        if (!queue.length) {
            if (deferredPlan) {
                var start = deferredPlanStart
                deferredPlan = false
                requestPlan(start)
            }
            return
        }
        var jobs = queue.slice(), job = jobs.shift()
        queue = jobs
        operation = job.kind
        pairSucceeded = false
        error = ""
        if (operation === "update") { updateReloadRequired = false; updateMessage = "" }
        actionInFlight = true
        action.command = [executable].concat(job.args)
        action.running = true
    }
    function parse(text, context) {
        try { return JSON.parse(text) }
        catch (exception) { error = "Zorya returned an invalid response."; captureError(error, context || "backend"); return null }
    }
    // Explicit user actions and panel opens poll at the base rate again.
    function userRefresh() { pollFailures = 0; refresh() }
    function refresh() {
        if (read.running || busy) { refreshRequested = true; return }
        refreshRequested = false
        readRevision = revision
        readKind = "status"
        read.command = [executable, "status"]
        read.running = true
    }
    function acceptAction(text) {
        var data = parse(text, operation)
        if (!data) return
        if (operation === "doctor" || operation === "setup") diagnostics = data
        if (operation === "pair") pairSucceeded = data.ok === true && !data.error
        error = data.error ? String(data.error) : ""
        if (data.ok === false && !error) error = "Could not complete " + operation + "."
        if (error) captureError(error, operation)
        if (operation === "update" && data.ok === true) {
            updateInfo = merged(updateInfo || {}, {update_available: false})
            updateReloadRequired = data.reload_required === true
            updateMessage = "Update installed."
        }
    }
    function acceptRead(text) {
        if (readRevision !== revision || busy) return
        var data = parse(text, readKind)
        if (!data) return
        if (readKind === "status") {
            state = merged(state, data)
            if (data.last_error && data.last_error.message && String(data.last_error.at) !== lastBackendErrorAt) {
                lastBackendErrorAt = String(data.last_error.at)
                captureError(data.last_error.message, data.last_error.operation || "backend", data.last_error.at)
            }
            error = data.error ? String(data.error) : ""
        } else {
            devices = Array.isArray(data.devices) ? data.devices : []
            if (data.error) error = String(data.error)
        }
        var message = data.error ? String(data.error) : ""
        pollFailures = message ? pollFailures + 1 : 0
        if (message && observedReadErrors[readKind] !== message && !data.last_error) captureError(message, readKind)
        observedReadErrors = merged(observedReadErrors, readKind === "status" ? {status: message} : {devices: message})
    }
    property Timer releasePoll: Timer { interval: 6 * 60 * 60 * 1000; repeat: true; running: true; onTriggered: service.checkUpdates(false) }
    property Timer debounce: Timer { interval: 120; onTriggered: service.commitPending() }
    property Timer poll: Timer { interval: Math.min(30000, 4000 * Math.pow(2, Math.min(service.pollFailures, 3))); repeat: true; running: service.active; onTriggered: service.refresh() }
    property Process action: Process {
        stdout: StdioCollector { onStreamFinished: service.acceptAction(text) }
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) service.error = text.trim().slice(0, 500); if (text.trim()) service.captureError(text.trim().slice(0, 500), service.operation) } }
        onExited: function(code) {
            service.actionInFlight = false
            if (code !== 0 && !service.error) service.error = "Could not complete " + service.operation + " (exit " + code + ")."
            if (code !== 0) service.captureError(service.error, service.operation)
            var refreshDoctor = service.operation === "pair" && code === 0 && service.pairSucceeded
            var reload = service.operation === "update" && code === 0 && service.updateReloadRequired
            Qt.callLater(function() {
                if (reload) { service.pluginReload.running = true; return }
                if (refreshDoctor) service.enqueue(["doctor"], "doctor")
                else service.next()
                if (!service.busy) service.refresh()
            })
        }
    }
    property Process read: Process {
        stdout: StdioCollector { onStreamFinished: service.acceptRead(text) }
        stderr: StdioCollector { onStreamFinished: { if (text.trim() && service.readRevision === service.revision && !service.busy) service.error = text.trim().slice(0, 500); if (text.trim() && service.readRevision === service.revision && !service.busy) service.captureError(text.trim().slice(0, 500), service.readKind) } }
        onExited: function(code) {
            if (code !== 0 && !service.error && service.readRevision === service.revision && !service.busy) service.error = "Zorya is unavailable. Open Setup to diagnose the backend."
            if (code !== 0) service.pollFailures += 1
            if (code !== 0 && service.error) service.captureError(service.error, service.readKind)
            if (service.queue.length && service.queue[0].kind === "update") { Qt.callLater(service.next); return }
            if (service.readKind === "status" && code === 0) {
                Qt.callLater(function() {
                    if (service.busy) return
                    service.readKind = "devices"
                    service.read.command = [service.executable, "devices"]
                    service.read.running = true
                })
            } else if (service.refreshRequested) Qt.callLater(service.refresh)
        }
    }
    Component.onCompleted: { refresh(); if (active && !planRequested) requestPlan(false); if (!updateChecked) checkUpdates(false) }
}
