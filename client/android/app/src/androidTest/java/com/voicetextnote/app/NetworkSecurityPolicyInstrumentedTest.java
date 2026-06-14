package com.voicetextnote.app;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.security.NetworkSecurityPolicy;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class NetworkSecurityPolicyInstrumentedTest {
    @Test
    public void debugBuildAllowsOnlyLocalAndTailscaleCleartext() {
        NetworkSecurityPolicy policy = NetworkSecurityPolicy.getInstance();

        assertTrue(policy.isCleartextTrafficPermitted("localhost"));
        assertTrue(policy.isCleartextTrafficPermitted("100.110.255.105"));
        assertFalse(policy.isCleartextTrafficPermitted("api.voicetextnote.com"));
        assertFalse(policy.isCleartextTrafficPermitted("example.com"));
    }
}
