import Testing
import Foundation
@testable import SheetLocalizer

@Suite
struct CSVParserTest {
    
    @Test
    func parseValidLocalizationCSV() throws {
        let result = try CSVParser.parse(SharedTestData.localizationCSV)
        
        #expect(result.count > 0)
        #expect(result[0].count >= 5) // Header row should have at least 5 columns
    }
    
    @Test
    func parseValidColorCSV() throws {
        let result = try CSVParser.parse(SharedTestData.colorsCSV)
        
        #expect(result.count > 0)
        #expect(result[0].count >= 5) // Header row should have at least 5 columns
    }
    
    @Test
    func parseEmptyCSV() throws {
        #expect(throws: SheetLocalizerError.self) {
            _ = try CSVParser.parse("")
        }
    }
    
    @Test
    func parseInvalidCSV() throws {
        let invalidCSV = "invalid,csv,without\nproper structure"
        
        #expect(throws: Never.self) {
            _ = try CSVParser.parse(invalidCSV)
        }
    }
    
    @Test
    func parseCSVWithQuotedFields() throws {
        let csvWithQuotes = """
        "[View]","[Item]","[Type]","en","es"
        "common","app_name","text","My App","Mi App"
        "login","title","text","Sign in","Iniciar sesión"
        """
        
        let result = try CSVParser.parse(csvWithQuotes)
        #expect(result.count == 3)
        #expect(result[1][3] == "My App")
        #expect(result[2][4] == "Iniciar sesión")
    }
    
}