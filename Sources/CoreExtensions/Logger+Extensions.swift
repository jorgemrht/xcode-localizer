import os.log
import Foundation

public enum LoggerCategory: String, CaseIterable, Sendable {
    case general
    case csv
    case parser
    case network
    case fileSystem
    case cli
    case xcodeIntegration
    case localizationGenerator
    case colorGenerator
    case urlTransformer
    
    public var logger: Logger {
        Logger(subsystem: "com.swiftsheetgen", category: rawValue)
    }
}

public extension Logger {
    static let shared = LoggerCategory.general.logger
    static let csvDownloader = LoggerCategory.csv.logger
    static let csvParser = LoggerCategory.parser.logger
    static let googleSheetURLTransformer = LoggerCategory.urlTransformer.logger
    static let xcodeIntegration = LoggerCategory.xcodeIntegration.logger
    static let cli = LoggerCategory.cli.logger
    static let fileSystem = LoggerCategory.fileSystem.logger
    static let network = LoggerCategory.network.logger
    static let localizationGenerator = LoggerCategory.localizationGenerator.logger
    static let colorGenerator = LoggerCategory.colorGenerator.logger
    
}