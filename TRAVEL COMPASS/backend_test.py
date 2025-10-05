import requests
import sys
import json
from datetime import datetime

class TravelGuideAPITester:
    def __init__(self, base_url="https://travel-compass-10.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Response: {data}"
            self.log_test("API Root Endpoint", success, details)
            return success
        except Exception as e:
            self.log_test("API Root Endpoint", False, str(e))
            return False

    def test_travel_recommendations(self, destination="Paris", preferences=None):
        """Test travel recommendations endpoint"""
        try:
            payload = {"destination": destination}
            if preferences:
                payload["preferences"] = preferences
            
            print(f"🔍 Testing recommendations for: {destination}")
            response = requests.post(
                f"{self.api_url}/recommendations", 
                json=payload,
                timeout=30  # AI responses can take time
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                # Validate response structure
                required_fields = ['id', 'query', 'recommendations', 'geographic_info', 'climate_info', 'created_at']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    success = False
                    details += f", Missing fields: {missing_fields}"
                else:
                    # Check if recommendations array has content
                    rec_count = len(data.get('recommendations', []))
                    geo_info = data.get('geographic_info', {})
                    climate_info = data.get('climate_info', {})
                    
                    details += f", Recommendations: {rec_count}, Geographic fields: {len(geo_info)}, Climate fields: {len(climate_info)}"
                    
                    # Validate that we have meaningful data
                    if rec_count == 0:
                        success = False
                        details += ", No recommendations returned"
                    
                    print(f"   📍 Query: {data.get('query')}")
                    print(f"   🏛️ Recommendations: {rec_count}")
                    print(f"   🌍 Geographic info: {len(geo_info)} fields")
                    print(f"   🌤️ Climate info: {len(climate_info)} fields")
            else:
                try:
                    error_data = response.json()
                    details += f", Error: {error_data}"
                except:
                    details += f", Response: {response.text[:200]}"
            
            self.log_test(f"Travel Recommendations ({destination})", success, details)
            return success, response.json() if success else None
            
        except Exception as e:
            self.log_test(f"Travel Recommendations ({destination})", False, str(e))
            return False, None

    def test_recommendations_history(self):
        """Test recommendations history endpoint"""
        try:
            response = requests.get(f"{self.api_url}/recommendations/history", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                if isinstance(data, list):
                    details += f", History count: {len(data)}"
                    print(f"   📚 History entries: {len(data)}")
                    
                    # Check structure of history items if any exist
                    if len(data) > 0:
                        first_item = data[0]
                        required_fields = ['id', 'query', 'recommendations', 'geographic_info', 'climate_info']
                        missing_fields = [field for field in required_fields if field not in first_item]
                        if missing_fields:
                            details += f", Missing fields in history: {missing_fields}"
                else:
                    success = False
                    details += ", Response is not a list"
            else:
                try:
                    error_data = response.json()
                    details += f", Error: {error_data}"
                except:
                    details += f", Response: {response.text[:200]}"
            
            self.log_test("Recommendations History", success, details)
            return success
            
        except Exception as e:
            self.log_test("Recommendations History", False, str(e))
            return False

    def test_status_endpoints(self):
        """Test status check endpoints"""
        try:
            # Test POST status
            test_client = f"test_client_{datetime.now().strftime('%H%M%S')}"
            response = requests.post(
                f"{self.api_url}/status",
                json={"client_name": test_client},
                timeout=10
            )
            
            post_success = response.status_code == 200
            details = f"POST Status: {response.status_code}"
            
            if post_success:
                data = response.json()
                required_fields = ['id', 'client_name', 'timestamp']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    post_success = False
                    details += f", Missing fields: {missing_fields}"
                else:
                    details += f", Client: {data.get('client_name')}"
            
            self.log_test("Status POST", post_success, details)
            
            # Test GET status
            response = requests.get(f"{self.api_url}/status", timeout=10)
            get_success = response.status_code == 200
            get_details = f"GET Status: {response.status_code}"
            
            if get_success:
                data = response.json()
                if isinstance(data, list):
                    get_details += f", Status entries: {len(data)}"
                else:
                    get_success = False
                    get_details += ", Response is not a list"
            
            self.log_test("Status GET", get_success, get_details)
            return post_success and get_success
            
        except Exception as e:
            self.log_test("Status Endpoints", False, str(e))
            return False

    def run_comprehensive_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting Travel Guide API Tests")
        print(f"🌐 Base URL: {self.base_url}")
        print("=" * 60)
        
        # Test basic connectivity
        if not self.test_api_root():
            print("❌ API root failed - stopping tests")
            return False
        
        # Test status endpoints
        self.test_status_endpoints()
        
        # Test travel recommendations with different destinations
        destinations = ["Paris", "Tokyo", "Bali"]
        successful_recommendations = 0
        
        for destination in destinations:
            success, _ = self.test_travel_recommendations(destination)
            if success:
                successful_recommendations += 1
        
        # Test with preferences
        success, _ = self.test_travel_recommendations("New York", "I love museums and fine dining")
        if success:
            successful_recommendations += 1
        
        # Test history endpoint
        self.test_recommendations_history()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {self.tests_run}")
        print(f"   Passed: {self.tests_passed}")
        print(f"   Failed: {self.tests_run - self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        print(f"   Successful Recommendations: {successful_recommendations}/4")
        
        # Check if critical functionality is working
        critical_success = successful_recommendations >= 2 and self.tests_passed >= (self.tests_run * 0.7)
        
        if critical_success:
            print("✅ Backend API is functioning well")
        else:
            print("❌ Backend API has significant issues")
        
        return critical_success

def main():
    tester = TravelGuideAPITester()
    success = tester.run_comprehensive_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())