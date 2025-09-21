import Testing
import Foundation
import CoreExtensions
@testable import SheetLocalizer

@Suite
struct CSVDownloaderTest {
    
    @Test
    func validGoogleSheetsURLRecognition() {
        let validURLs = [
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vRj3aWiQffPzhrWzu1E8B14_3YiqQ_uwh3K0yVANXJuUpCS3fJ523VIu3VDNyRnXQ5jCWeN3AL9XX0a/pubhtml",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vRj3aWiQffPzhrWzu1E8B14_3YiqQ_uwh3K0yVANXJuUpCS3fJ523VIu3VDNyRnXQ5jCWeN3AL9XX0a/pub?output=csv"
        ]
        
        for url in validURLs {
            #expect(url.isGoogleSheetsURL)
        }
    }
    
    @Test 
    func invalidURLRejection() {
        let invalidURLs = [
            "https://google.com",
            "https://docs.google.com/documents/d/123/edit",
            "https://sheets.google.com/invalid",
            ""
        ]
        
        for url in invalidURLs {
            #expect(!url.isGoogleSheetsURL)
        }
    }
    
    @Test
    func emptyURLInputValidation() async {
        let downloader = CSVDownloader(timeoutInterval: 0.1)
        let tempDir = SharedTestData.createTempDirectory()
        let outputPath = tempDir.appendingPathComponent("output.csv").path
        
        await #expect(throws: SheetLocalizerError.self) {
            try await downloader.download(from: "", to: outputPath)
        }
    }
    
    @Test
    func emptyOutputPathValidation() async {
        let downloader = CSVDownloader(timeoutInterval: 0.1)
        let validURL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRj3aWiQffPzhrWzu1E8B14_3YiqQ_uwh3K0yVANXJuUpCS3fJ523VIu3VDNyRnXQ5jCWeN3AL9XX0a/pubhtml"
        
        await #expect(throws: SheetLocalizerError.self) {
            try await downloader.download(from: validURL, to: "")
        }
    }
    
    @Test
    func validOutputPathCreation() async {
        let downloader = CSVDownloader(timeoutInterval: 0.1)
        let validURL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRj3aWiQffPzhrWzu1E8B14_3YiqQ_uwh3K0yVANXJuUpCS3fJ523VIu3VDNyRnXQ5jCWeN3AL9XX0a/pubhtml"
        
        let tempDir = FileManager.default.temporaryDirectory
        let fullPath = tempDir.appendingPathComponent("test_output.csv").path
        
        // This should not throw for path creation
        await #expect(throws: Never.self) {
            // URL will fail network wise, but path validation should pass
            do {
                try await downloader.download(from: validURL, to: fullPath)
            } catch SheetLocalizerError.fileSystemError {
                throw SheetLocalizerError.fileSystemError("Path validation failed")
            } catch {
                // Network errors are expected for test URLs
            }
        }
    }
}