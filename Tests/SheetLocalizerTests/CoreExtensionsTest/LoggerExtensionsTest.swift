import Testing
import os.log
@testable import CoreExtensions
import Foundation

@Suite
struct LoggerExtensionsTest {
    
    @Test
    func loggerModuleSpecificLoggersAvailable() {
        #expect(throws: Never.self) {
            _ = Logger.csvDownloader
            _ = Logger.csvParser
            _ = Logger.googleSheetURLTransformer
            _ = Logger.xcodeIntegration
            _ = Logger.cli
            _ = Logger.fileSystem
            _ = Logger.network
            _ = Logger.localizationGenerator
            _ = Logger.colorGenerator
            _ = Logger.shared
        }
    }
    
    @Test
    func loggerSharedInstancesConsistency() {
        #expect(throws: Never.self) {
            let logger1 = Logger.csvDownloader
            let logger2 = Logger.csvParser  
            let logger3 = Logger.shared
            
            logger1.info("Test message")
            logger2.info("Test message")
            logger3.info("Test message")
        }
    }
}