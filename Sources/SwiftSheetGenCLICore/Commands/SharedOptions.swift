import ArgumentParser

public struct SharedOptions: ParsableArguments {
    @Argument(help: "📊 Google Sheets URL (must be publicly accessible)")
    public var sheetsURL: String

    @Option(name: .long, help: "📁 Target directory for generated files (default: current directory)")
    public var outputDir: String = "./"

    @Flag(name: .long, help: "💾 Keep downloaded CSV file for debugging")
    public var keepCSV: Bool = false

    public init() {}
}
