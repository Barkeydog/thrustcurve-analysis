
import { ThrustCurveAPI } from '@thrustcurve/api1';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Infer types from the library since they aren't exported
type SearchRequest = Parameters<ThrustCurveAPI['searchMotors']>[0];
type SearchResponse = Awaited<ReturnType<ThrustCurveAPI['searchMotors']>>;

// Define interface for our calculated data
interface MotorAnalysis {
    id: string;
    designation: string;
    manufacturer: string;
    commonName: string;

    // Thrust Ratios
    thrustToWeightRatio: number;
    thrustToSizeRatio: number;

    // Impulse Ratios
    impulseToWeightRatio: number;
    impulseToSizeRatio: number;

    // New Metric
    specificImpulseSec: number;

    // Raw Data
    avgThrustN: number;
    totImpulseNs: number;
    totalWeightG: number;
    propWeightG: number;
    diameter: number;
    length: number;
    type: string;
}

async function main() {
    const api = new ThrustCurveAPI();

    console.log('Fetching all motors...');

    // We need to fetch all motors. 
    // The API documentation suggests using search with minimal criteria to get a broad set.
    // There isn't a dedicated "get all" endpoint, but a broad search works.
    // We use a high maxResults to try and get everything.
    // Pagination isn't explicitly detailed as a standard "page 1, page 2" in the simple search examples, 
    // but maxResults is key.

    // NOTE: The Swagger docs say "maxResults: maximum number of motors to return".
    // Getting ALL motors might require multiple requests if there's a hard limit, 
    // but let's start with a large number.
    const searchRequest: SearchRequest = {
        maxResults: 9999,
        availability: 'all'
    };

    try {
        const response = await api.searchMotors(searchRequest);

        if (!response.results || response.results.length === 0) {
            console.error('No motors found!');
            return;
        }

        console.log(`Found ${response.results.length} motors. Processing...`);

        const validMotors: MotorAnalysis[] = [];

        for (const motor of response.results) {
            // Validation: Ensure valid numbers for calculations
            // avgThrustN: Newtons
            // totalWeightG: Grams. We need to convert to Newtons (Weight = Mass * Gravity)
            // diameter: mm
            // length: mm

            if (
                motor.avgThrustN != null && motor.avgThrustN > 0 &&
                motor.totImpulseNs != null && motor.totImpulseNs > 0 &&
                motor.totalWeightG != null && motor.totalWeightG > 0 &&
                motor.propWeightG != null && motor.propWeightG > 0 &&
                motor.diameter != null && motor.diameter > 0 &&
                motor.length != null && motor.length > 0 &&
                motor.motorId &&
                motor.commonName &&
                motor.type !== 'hybrid'
            ) {
                // Calculate Weight in Newtons
                // totalWeightG is in grams. 
                // kg = g / 1000
                // Weight (N) = kg * 9.80665
                const weightN = (motor.totalWeightG / 1000) * 9.80665;

                // Calculate Volume in mm^3 (Cylinder approximation)
                // Volume = Pi * r^2 * h
                // r = diameter / 2
                const radius = motor.diameter / 2;
                const volumeMm3 = Math.PI * Math.pow(radius, 2) * motor.length;

                // --- Thrust Calculations ---
                const thrustToWeightRatio = motor.avgThrustN / weightN;
                const thrustToSizeRatio = motor.avgThrustN / volumeMm3;

                // --- Impulse Calculations ---
                // Impulse / Weight (N-s / N) = Seconds (Specific Efficiency metric)
                const impulseToWeightRatio = motor.totImpulseNs / weightN;

                // Impulse / Size ratio (N-s / mm^3)
                const impulseToSizeRatio = motor.totImpulseNs / volumeMm3;

                // --- Specific Impulse (Isp) ---
                // Isp = Total Impulse / (Propellant Mass * g)
                const propWeightKg = motor.propWeightG / 1000;
                const propWeightN = propWeightKg * 9.80665;
                const specificImpulseSec = motor.totImpulseNs / propWeightN;

                validMotors.push({
                    id: motor.motorId,
                    designation: motor.designation || 'N/A',
                    manufacturer: motor.manufacturer || 'Unknown',
                    commonName: motor.commonName,

                    thrustToWeightRatio: thrustToWeightRatio,
                    thrustToSizeRatio: thrustToSizeRatio,
                    impulseToWeightRatio: impulseToWeightRatio,
                    impulseToSizeRatio: impulseToSizeRatio,
                    specificImpulseSec: specificImpulseSec,

                    avgThrustN: motor.avgThrustN,
                    totImpulseNs: motor.totImpulseNs,
                    totalWeightG: motor.totalWeightG,
                    propWeightG: motor.propWeightG,
                    diameter: motor.diameter,
                    length: motor.length,
                    type: motor.type || 'Unknown'
                });
            }
        }

        console.log(`Processed ${validMotors.length} valid motors for analysis.`);


        console.log(`Processed ${validMotors.length} valid motors for analysis.`);

        // Generate reports for all valid motors
        generateReports(validMotors, '');

        // Generate reports for motors under 640 Ns
        const motorsUnder640 = validMotors.filter(m => m.totImpulseNs < 640);
        console.log(`Found ${motorsUnder640.length} motors under 640 Ns.`);
        generateReports(motorsUnder640, '_under_640ns');

        // Export to JSON for Python visualization
        const jsonOutput = path.join(__dirname, '../motors_under_640ns.json');
        fs.writeFileSync(jsonOutput, JSON.stringify(motorsUnder640, null, 2));
        console.log(`Exported JSON data: ${jsonOutput}`);

    } catch (error) {
        console.error('Error fetching or processing data:', error);
    }
}

function generateReports(motors: MotorAnalysis[], suffix: string) {
    if (motors.length === 0) {
        console.log(`No motors to report for suffix: ${suffix}`);
        return;
    }

    // --- Generate Thrust Report ---
    const topThrustWeight = [...motors].sort((a, b) => b.thrustToWeightRatio - a.thrustToWeightRatio).slice(0, 10);
    const topThrustSize = [...motors].sort((a, b) => b.thrustToSizeRatio - a.thrustToSizeRatio).slice(0, 10);

    let reportThrust = `ThrustCurve Top 10 Motor Analysis (Thrust)${suffix ? ` [${suffix}]` : ''}\n`;
    reportThrust += '==========================================\n\n';

    reportThrust += 'Top 10 Motors by Thrust / Weight Ratio (N/N)\n';
    reportThrust += '--------------------------------------------\n';
    topThrustWeight.forEach((m, index) => {
        reportThrust += `${index + 1}. ${m.manufacturer} ${m.commonName} (${m.type})\n`;
        reportThrust += `   Ratio: ${m.thrustToWeightRatio.toFixed(2)}\n`;
        reportThrust += `   Thrust: ${m.avgThrustN} N, Weight: ${m.totalWeightG} g\n\n`;
    });

    reportThrust += 'Top 10 Motors by Thrust / Size Ratio (N/mm^3)\n';
    reportThrust += '---------------------------------------------\n';
    topThrustSize.forEach((m, index) => {
        reportThrust += `${index + 1}. ${m.manufacturer} ${m.commonName} (${m.type})\n`;
        reportThrust += `   Ratio: ${m.thrustToSizeRatio.toExponential(4)}\n`;
        reportThrust += `   Thrust: ${m.avgThrustN} N, Size: ${m.diameter}mm x ${m.length}mm\n\n`;
    });

    const outputThrust = path.join(__dirname, `../top_motors_thrust${suffix}.txt`);
    fs.writeFileSync(outputThrust, reportThrust);
    console.log(`Generated: ${outputThrust}`);

    // --- Generate Impulse Report ---
    const topImpulseWeight = [...motors].sort((a, b) => b.impulseToWeightRatio - a.impulseToWeightRatio).slice(0, 10);
    const topImpulseSize = [...motors].sort((a, b) => b.impulseToSizeRatio - a.impulseToSizeRatio).slice(0, 10);

    let reportImpulse = `ThrustCurve Top 10 Motor Analysis (Total Impulse)${suffix ? ` [${suffix}]` : ''}\n`;
    reportImpulse += '==================================================\n\n';

    reportImpulse += 'Top 10 Motors by Impulse / Weight Ratio (N-s/N)\n';
    reportImpulse += '-----------------------------------------------\n';
    topImpulseWeight.forEach((m, index) => {
        reportImpulse += `${index + 1}. ${m.manufacturer} ${m.commonName} (${m.type})\n`;
        reportImpulse += `   Ratio: ${m.impulseToWeightRatio.toFixed(2)}\n`;
        reportImpulse += `   Impulse: ${m.totImpulseNs} N-s, Weight: ${m.totalWeightG} g\n\n`;
    });

    reportImpulse += 'Top 10 Motors by Impulse / Size Ratio (N-s/mm^3)\n';
    reportImpulse += '------------------------------------------------\n';
    topImpulseSize.forEach((m, index) => {
        reportImpulse += `${index + 1}. ${m.manufacturer} ${m.commonName} (${m.type})\n`;
        reportImpulse += `   Ratio: ${m.impulseToSizeRatio.toExponential(4)}\n`;
        reportImpulse += `   Impulse: ${m.totImpulseNs} N-s, Size: ${m.diameter}mm x ${m.length}mm\n\n`;
    });

    const outputImpulse = path.join(__dirname, `../top_motors_impulse${suffix}.txt`);
    fs.writeFileSync(outputImpulse, reportImpulse);
    console.log(`Generated: ${outputImpulse}`);

    // --- Generate Specific Impulse Report ---
    const topIsp = [...motors].sort((a, b) => b.specificImpulseSec - a.specificImpulseSec).slice(0, 10);

    let reportIsp = `ThrustCurve Top 10 Motor Analysis (Specific Impulse)${suffix ? ` [${suffix}]` : ''}\n`;
    reportIsp += '====================================================\n\n';

    reportIsp += 'Top 10 Motors by Specific Impulse (Isp)\n';
    reportIsp += '---------------------------------------\n';
    topIsp.forEach((m, index) => {
        reportIsp += `${index + 1}. ${m.manufacturer} ${m.commonName} (${m.type})\n`;
        reportIsp += `   Isp: ${m.specificImpulseSec.toFixed(2)} s\n`;
        reportIsp += `   Impulse: ${m.totImpulseNs} N-s, Prop Weight: ${m.propWeightG} g\n\n`;
    });

    const outputIsp = path.join(__dirname, `../top_motors_specificimpulse${suffix}.txt`);
    fs.writeFileSync(outputIsp, reportIsp);
    console.log(`Generated: ${outputIsp}`);
}

main();

