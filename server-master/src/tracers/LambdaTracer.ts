import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import express from 'express';
import { Release, Tracer } from 'tracers/Tracer';
import { awsAccessKeyId, awsSecretAccessKey } from 'config/environments';
import { BadRequest } from 'ts-httpexceptions';

export class LambdaTracer extends Tracer {
  static lambda = new LambdaClient({
    region: 'us-east-2',
    credentials: {
      accessKeyId: awsAccessKeyId,
      secretAccessKey: awsSecretAccessKey,
    },
  });

  async build(release: Release) {
  }

  route(router: express.Router) {
    router.post(`/${this.lang}`, async (req, res, next) => {
      const {code} = req.body;
      try {
        const command = new InvokeCommand({
          FunctionName: `extractor-${this.lang}`,
          InvocationType: 'RequestResponse',
          Payload: JSON.stringify(code),
        });

        const response = await LambdaTracer.lambda.send(command);

        if (!response.Payload) {
          return next(new Error('No payload received'));
        }

        // Convert Uint8Array to string
        const payloadString = Buffer.from(response.Payload).toString();
        const payload = JSON.parse(payloadString);

        if (!payload.success) {
          return next(new BadRequest(payload.errorMessage));
        }

        res.send(payload.commands);
      } catch (err) {
        next(err);
      }
    });
  }
}
