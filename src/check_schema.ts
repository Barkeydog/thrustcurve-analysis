
import { ThrustCurveAPI } from '@thrustcurve/api1';

async function main() {
    const api = new ThrustCurveAPI();
    try {
        const response = await api.searchMotors({
            maxResults: 1,
            availability: 'all'
        });

        if (response.results && response.results.length > 0) {
            console.log(JSON.stringify(response.results[0], null, 2));
        } else {
            console.log("No motors found.");
        }
    } catch (error) {
        console.error(error);
    }
}

main();
