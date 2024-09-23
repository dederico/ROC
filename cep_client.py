import requests

class CepClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_cep_pdf(self, tipoCriterio, fecha, criterio, emisor, receptor, cuenta, receptorParticipante, monto, testCaseId=None):
        url = f"{self.base_url}/cep/validate+pdf"
        body = {
            "tipoCriterio": tipoCriterio,
            "fecha": fecha,
            "criterio": criterio,
            "emisor": emisor,
            "receptor": receptor,
            "cuenta": cuenta,
            "receptorParticipante": receptorParticipante,
            "monto": monto
        }
        
        params = {}
        if testCaseId:
            params['testCaseId'] = testCaseId
        
        response = requests.post(url, headers=self.headers, json=body, params=params)

        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Error: No se pudo decodificar la respuesta como JSON. Código de estado: {response.status_code}")
            return
        
        if response.status_code == 200:
            files_path = response_json.get('apiData', [{}])[0].get('files', [{}])[0].get('path')
            if files_path:
                return self.download_pdf(files_path)
            else:
                print("No se encontró el archivo en la respuesta.")
        else:
            print(f"Error: {response.status_code}, {response.text}")

    def download_pdf(self, path):
        file_url = f"{self.base_url}/{path}"
        print(f"URL del archivo PDF: {file_url}")  # Imprimir la URL para verificarla
        response = requests.get(file_url, headers=self.headers)
        
        if response.status_code == 200:
            with open("CEP.pdf", "wb") as f:
                f.write(response.content)
            print("PDF descargado exitosamente.")
        else:
            print(f"Error al descargar el PDF: {response.status_code}")

if __name__ == "__main__":
    # Configuración del cliente
    base_url = "https://sandbox.link.kiban.com/api/v2"
    api_key = "1KBNR7H29S4TVS-212P5E6000017M-BMHJ-1FTSFN4FN"
    
    # Parámetros requeridos
    tipoCriterio = "R"
    fecha = "2024-07-24"
    criterio = "Reference Number"
    emisor = "40012"
    receptor = "90659"
    cuenta = "2407240"
    receptorParticipante = True
    monto = 1320.00

    # Test case opcional
    testCaseId = "663567bb713cf2110a1106a1"

    client = CepClient(base_url, api_key)
    client.get_cep_pdf(tipoCriterio, fecha, criterio, emisor, receptor, cuenta, receptorParticipante, monto, testCaseId)
