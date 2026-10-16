import QtQuick
import Quickshell.Io

// Quickshell's tooling metadata omits QProcess::ExitStatus; runtime exit
// signals are covered by the offscreen process integration test.
// qmllint disable signal-handler-parameters

QtObject {
    id: service
    readonly property string executable: String(Qt.resolvedUrl("bin/zorya-rgb")).replace(/^file:\/\//, "")
    property var state: ({on: true, color: "#FFFFFF", brightness: 100, effect: "static", speed: 1, secondary_color: "#8A6CFF", devices: [], presets: [], connected: false})
    property var devices: []
    property var diagnostics: null
    property string error: ""
    property bool active: false
    readonly property bool busy: planLoading || setupRunning || action.running || queue.length > 0 || Object.keys(pending).length > 0
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
    onActiveChanged: { if (active && !planRequested) requestPlan(false) }

    function requestPlan(start) {
        if (onboarding.running || setupRunning || planLoading) return
        commitPending()
        if (action.running || queue.length) {
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
        commitPending()
        enqueue(args, kind || args[0])
    }
    function next() {
        if (action.running || setupRunning || planLoading) return
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
        action.command = [executable].concat(job.args)
        action.running = true
    }
    function parse(text) {
        try { return JSON.parse(text) }
        catch (exception) { error = "Zorya returned an invalid response. " + String(text).slice(0, 180); return null }
    }
    function refresh() {
        if (read.running || busy) { refreshRequested = true; return }
        refreshRequested = false
        readRevision = revision
        readKind = "status"
        read.command = [executable, "status"]
        read.running = true
    }
    function acceptAction(text) {
        var data = parse(text)
        if (!data) return
        if (operation === "doctor" || operation === "setup") diagnostics = data
        if (operation === "pair") pairSucceeded = data.ok === true && !data.error
        error = data.error ? String(data.error) : ""
    }
    function acceptRead(text) {
        if (readRevision !== revision || busy) return
        var data = parse(text)
        if (!data) return
        if (readKind === "status") {
            state = merged(state, data)
            error = data.error ? String(data.error) : ""
        } else {
            devices = Array.isArray(data.devices) ? data.devices : []
            if (data.error) error = String(data.error)
        }
    }
    property Timer debounce: Timer { interval: 120; onTriggered: service.commitPending() }
    property Timer poll: Timer { interval: 4000; repeat: true; running: service.active; onTriggered: service.refresh() }
    property Process action: Process {
        stdout: StdioCollector { onStreamFinished: service.acceptAction(text) }
        stderr: StdioCollector { onStreamFinished: { if (text.trim()) service.error = text.trim().slice(0, 500) } }
        onExited: function(code) {
            if (code !== 0 && !service.error) service.error = "Could not complete " + service.operation + " (exit " + code + ")."
            var refreshDoctor = service.operation === "pair" && code === 0 && service.pairSucceeded
            Qt.callLater(function() {
                if (refreshDoctor) service.enqueue(["doctor"], "doctor")
                else service.next()
                if (!service.busy) service.refresh()
            })
        }
    }
    property Process read: Process {
        stdout: StdioCollector { onStreamFinished: service.acceptRead(text) }
        stderr: StdioCollector { onStreamFinished: { if (text.trim() && service.readRevision === service.revision && !service.busy) service.error = text.trim().slice(0, 500) } }
        onExited: function(code) {
            if (code !== 0 && !service.error && service.readRevision === service.revision && !service.busy) service.error = "Zorya is unavailable. Open Setup to diagnose the backend."
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
    Component.onCompleted: { refresh(); if (active && !planRequested) requestPlan(false) }
}
