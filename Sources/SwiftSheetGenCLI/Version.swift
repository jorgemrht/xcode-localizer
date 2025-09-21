import Foundation

public struct AppVersion {
    public static let current: String = {
        return ProcessInfo.processInfo.environment["SWIFTSHEETGEN_VERSION"] ?? "0.0.0-development"
    }()
}