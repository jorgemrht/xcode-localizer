import Foundation
import ArgumentParser
import os.log

public extension AsyncParsableCommand {
  
    func validateGoogleSheetsURL(_ urlString: String) -> Bool {
        urlString.isGoogleSheetsURL
    }
    
    func ensureOutputDirectoryExists(atPath path: String, logger: Logger) throws {
        let trimmedPath = path.trimmingCharacters(in: .whitespacesAndNewlines)
        try FileManager.default.createDirectoryIfNeeded(atPath: trimmedPath)
    }

    func logSuccessfulExecutionCompletion(
        startTime: Date,
        generatedFilesLocation: String
    ) {
        let executionDuration = Date().timeIntervalSince(startTime)
        let logger = Logger.cli
        
        logger.log("✅ Generation completed in \(String(format: "%.2f", executionDuration)) seconds")
        logger.log("📁 Files generated in: \(generatedFilesLocation)")
    }
}