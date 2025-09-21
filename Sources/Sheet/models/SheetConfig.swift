import Foundation

public protocol SheetConfig: Sendable {
    var outputDirectory: String { get }
    var csvFileName: String { get }
    var cleanupTemporaryFiles: Bool { get }
}