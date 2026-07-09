using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace UnlockECU
{
    /// <summary>
    /// Very similar implementation to Mattwmaster58's IC204, except this splits out the key expansion level
    /// </summary>
    class VDOSecurityAlgo : SecurityProvider
    {
        public override bool GenerateKey(byte[] inSeed, byte[] outKey, int accessLevel, List<Parameter> parameters)
        {
            byte[] kc = GetParameterBytearray(parameters, "K");
            int keyExpansionLevel = GetParameterInteger(parameters, "InternalLevel");

            if ((inSeed.Length != 8) || (outKey.Length != 8))
            {
                return false;
            }

            byte[] result = GenerateKey(keyExpansionLevel, inSeed, kc);
            Array.ConstrainedCopy(result, 0, outKey, 0, inSeed.Length);
            return true;
        }

        public override string GetProviderName()
        {
            return "VDOSecurityAlgo";
        }

        private byte[] GenerateKey(int keyExpansionLevel, byte[] seed, byte[] kc, int tpcScramblerLevel = -1)
        {
            if (tpcScramblerLevel == -1)
            {
                tpcScramblerLevel = keyExpansionLevel;
            }

            byte[] tp = new byte[]
            {
                seed[7], seed[4], seed[3], seed[6],
                seed[5], seed[1], seed[0], seed[2],
            };
            byte[] ik = ExpandAndTransformKey(keyExpansionLevel, tp, kc); // sp[8-f]

            byte[] tpc = new byte[] { tp[0], tp[1], tp[2], tp[3], tp[4], tp[5], tp[6], tp[7] }; // sp[0-7]

            for (int cipherIter = 0; cipherIter < 2; cipherIter++)
            {
                for (int i = 0; i < 4; i++)
                {
                    tp[i] ^= tp[4 + i];
                }

                int rotateCount = tpc[tpcScramblerLevel] & 3;
                rotateCount++;

                byte[] lowerRotateBytes = new byte[] { tp[0], tp[1], tp[2], tp[3] };

                for (int i = 0; i < rotateCount; i++)
                {
                    RotateBits(lowerRotateBytes);
                }
                tp[0] = lowerRotateBytes[0];
                tp[1] = lowerRotateBytes[1];
                tp[2] = lowerRotateBytes[2];
                tp[3] = lowerRotateBytes[3];


                uint tpSum = tp[0];
                tpSum |= (uint)(tp[1] << 8);
                tpSum |= (uint)(tp[2] << 16);
                tpSum |= (uint)(tp[3] << 24);

                uint ikSum = ik[0];
                ikSum |= (uint)(ik[1] << 8);
                ikSum |= (uint)(ik[2] << 16);
                ikSum |= (uint)(ik[3] << 24);

                unchecked
                {
                    tpSum += ikSum;
                }
                tp[0] = (byte)((tpSum >> 0) & 0xFF);
                tp[1] = (byte)((tpSum >> 8) & 0xFF);
                tp[2] = (byte)((tpSum >> 16) & 0xFF);
                tp[3] = (byte)((tpSum >> 24) & 0xFF);

                tp[4] = tpc[0];
                tp[5] = tpc[1];
                tp[6] = tpc[2];
                tp[7] = tpc[3];

                Array.ConstrainedCopy(tp, 0, tpc, 0, 8);

                for (int i = 0; i < 4; i++)
                {
                    tp[i] ^= tp[4 + i];
                }

                int rotateCount2 = tpc[tpcScramblerLevel] & 3;
                rotateCount2++;
                
                byte[] lowerRotateBytes2 = new byte[] { tp[0], tp[1], tp[2], tp[3] };

                for (int i = 0; i < rotateCount2; i++)
                {
                    RotateBits(lowerRotateBytes2);
                }
                tp[0] = lowerRotateBytes2[0];
                tp[1] = lowerRotateBytes2[1];
                tp[2] = lowerRotateBytes2[2];
                tp[3] = lowerRotateBytes2[3];

                uint tpSum2 = tp[0];
                tpSum2 |= (uint)(tp[1] << 8);
                tpSum2 |= (uint)(tp[2] << 16);
                tpSum2 |= (uint)(tp[3] << 24);

                uint ikSum2 = ik[4];
                ikSum2 |= (uint)(ik[5] << 8);
                ikSum2 |= (uint)(ik[6] << 16);
                ikSum2 |= (uint)(ik[7] << 24);

                unchecked
                {
                    tpSum2 += ikSum2;
                }
                tp[0] = (byte)((tpSum2 >> 0) & 0xFF);
                tp[1] = (byte)((tpSum2 >> 8) & 0xFF);
                tp[2] = (byte)((tpSum2 >> 16) & 0xFF);
                tp[3] = (byte)((tpSum2 >> 24) & 0xFF);

                tp[4] = tpc[0];
                tp[5] = tpc[1];
                tp[6] = tpc[2];
                tp[7] = tpc[3];

                Array.ConstrainedCopy(tp, 0, tpc, 0, 8);
            }

            byte[] key = new byte[] {
                tpc[3], tpc[5], tpc[6], tpc[1],
                tpc[0], tpc[7], tpc[4], tpc[2],
            };
            return key;
        }

        private byte[] ExpandAndTransformKey(int accessLevel, byte[] transposedSeed, byte[] kc)
        {
            int morphCount = (transposedSeed[accessLevel] & 7) + 2;
            ExpandFullKey(kc);

            byte[] mKey = new byte[] { 0, 0, 0, 0, 0, 0, 0, 0 };
            Array.ConstrainedCopy(kc, 0, mKey, 0, 8);

            for (int i = 0; i < morphCount; i++)
            {
                byte[] ek = new byte[]
                {
                    mKey[0], mKey[1], mKey[2], mKey[3],
                    mKey[4], mKey[5], mKey[6], mKey[7]
                };

                byte xorIntermediate = 0;

                ek[0] &= 8;
                ek[0] >>= 3;

                xorIntermediate ^= ek[0];

                ek[1] &= 1;
                ek[1] >>= 0;

                xorIntermediate ^= ek[1];

                ek[2] &= 2;
                ek[2] >>= 1;

                xorIntermediate ^= ek[2];

                ek[3] &= 0x80;
                ek[3] >>= 7;

                xorIntermediate ^= ek[3];

                ek[4] &= 0x20;
                ek[4] >>= 5;

                xorIntermediate ^= ek[4];

                ek[5] &= 4;
                ek[5] >>= 2;

                xorIntermediate ^= ek[5];

                ek[6] &= 0x40;
                ek[6] >>= 6;

                xorIntermediate ^= ek[6];

                byte snapshot = ek[7];
                ek[7] &= 0x10;
                ek[7] >>= 4;

                xorIntermediate ^= ek[7];

                byte finalByteTransformed = (byte)(xorIntermediate << 7);
                finalByteTransformed |= (byte)(snapshot & 0x7F);

                mKey[7] = finalByteTransformed;
                RotateBits(mKey);

            }
            return mKey;
        }

        private void ExpandFullKey(byte[] keyConstant)
        {
            byte[] keyLower = new byte[] { keyConstant[0], keyConstant[1], keyConstant[2], keyConstant[3] };
            byte[] keyUpper = new byte[] { keyConstant[4], keyConstant[5], keyConstant[6], keyConstant[7] };
            Expand32BitKey(keyLower);
            Expand32BitKey(keyUpper);
            Array.ConstrainedCopy(keyLower, 0, keyConstant, 0, keyLower.Length);
            Array.ConstrainedCopy(keyUpper, 0, keyConstant, 4, keyUpper.Length);
        }

        private void Expand32BitKey(byte[] key)
        {
            byte[] keyA = new byte[] { key[0], key[1], key[2], key[3] };
            byte[] keyP = new byte[] { key[1], key[3], key[0], key[2] };

            int rotateCountP = (key[2] & 0xF) + 1;
            RotateBits(keyP, rotateCountP);

            int rotateCountA = (key[3] & 0xF) + 1;
            RotateBits(keyA, rotateCountA);

            for (int i = 0; i < key.Length; i++)
            {
                key[i] = (byte)(keyA[i] ^ keyP[i]);
            }
        }
        private void RotateBits(byte[] inBytes, int count)
        {
            for (int i = 0; i < count; i++)
            {
                RotateBits(inBytes);
            }
        }
        private void RotateBits(byte[] inBytes)
        {
            byte[] tempBuffer = new byte[inBytes.Length];
            for (int i = 0; i < tempBuffer.Length; i++)
            {
                if ((inBytes[i] & 1) > 0)
                {
                    tempBuffer[i] = 0x80;
                }
            }
            for (int i = 0; i < tempBuffer.Length; i++)
            {
                int rIndex = i - 1;
                if (rIndex < 0)
                {
                    rIndex = tempBuffer.Length - 1;
                }
                inBytes[i] = (byte)(inBytes[i] >> 1);
                inBytes[i] |= tempBuffer[rIndex];
            }
        }
    }
}
