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
    readonly property bool busy: action.running || queue.length > 0 || Object.keys(pending).length > 0
    property string operation: ""
    property var pending: ({})
    property var queue: []
    property int revision: 0
    property int readRevision: 0
    property string readKind: "status"
    property bool refreshRequested: false
    property bool pairSucceeded: false

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
        debounce.restart()
    }
    function commitPending() {
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
        if (action.running || !queue.length) return
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
    Component.onCompleted: refresh()
}
